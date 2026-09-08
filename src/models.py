"""模型下载与就绪状态 —— 让用户看到"要下多大、下到哪了、好没好"。

faster-whisper 的模型放在 HuggingFace 缓存里, 首次用 WhisperModel() 时会
阻塞下载、无进度。这里: 查就绪 / 估算大小 / 带进度下载(轮询磁盘字节算%)。
"""
import glob
import os
import threading
import time

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
# 下载源(按顺序试, 哪个成功用哪个):
#   用户自设 HF_ENDPOINT > huggingface.co 官方 > hf-mirror.com。
# 教训(2026-09-09 新用户模拟实测): 曾把 HF_ENDPOINT 默认写死成 hf-mirror.com —— 该站
# 已变成对 huggingface.co 的 308 跳转(等于关站), huggingface_hub 检测到跨域直接抛
# "Distant resource does not seem to be on huggingface.co", 挂着梯子也下不了。
# 所以: 不再全局改 HF_ENDPOINT(会连累 faster-whisper 自己的缓存解析), 只在 download()
# 里按 endpoint 参数逐个试; 全失败就明确告诉用户"连不上, 需代理或手动放模型"。
def endpoints():
    seen, out = set(), []
    for e in (os.environ.get("HF_ENDPOINT"), "https://huggingface.co", "https://hf-mirror.com"):
        e = (e or "").strip().rstrip("/")
        if e and e not in seen:
            seen.add(e)
            out.append(e)
    return out


class ModelDownloadError(RuntimeError):
    """所有下载源都失败。message 已是给用户看的一句话。"""

# 语言中立写法 (≈), 中英 UI 都能直接嵌用
_SIZE = {
    "tiny": "≈ 75 MB", "base": "≈ 145 MB", "small": "≈ 480 MB",
    "medium": "≈ 1.5 GB", "large-v3": "≈ 3 GB", "large-v3-turbo": "≈ 1.6 GB",
}
_CACHE = os.path.expanduser("~/.cache/huggingface/hub")


def model_repo(model):
    try:
        from faster_whisper.utils import _MODELS
        return _MODELS.get(model, model)
    except Exception:
        return model


def _cache_dir(model):
    return os.path.join(_CACHE, "models--" + model_repo(model).replace("/", "--"))


def is_ready(model):
    """模型是否已完整下载 (缓存里有像样的 model.bin)。"""
    if model in (None, "", "auto"):
        return True
    d = _cache_dir(model)
    if not os.path.isdir(d):
        return False
    bins = glob.glob(os.path.join(d, "snapshots", "*", "model.bin"))
    bins += glob.glob(os.path.join(d, "blobs", "*"))
    return any(os.path.getsize(b) > 20_000_000 for b in bins)


def size_hint(model):
    return _SIZE.get(model, "?")


def _repo_total_bytes(repo, endpoint=None):
    try:
        from huggingface_hub import HfApi
        info = HfApi(endpoint=endpoint).model_info(repo, files_metadata=True)
        return sum((s.size or 0) for s in info.siblings)
    except Exception:
        return 0


def _snapshot(repo, endpoint):
    """真正的下载动作(单独成函数便于测试替换)。"""
    from huggingface_hub import snapshot_download
    snapshot_download(repo, endpoint=endpoint)


def _downloaded_bytes(model):
    """已下到磁盘的字节 (数 blobs/, 就是真正的下载内容)。"""
    d = _cache_dir(model)
    blobs = os.path.join(d, "blobs")
    root = blobs if os.path.isdir(blobs) else d
    total = 0
    for dp, _, files in os.walk(root):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(dp, f))
            except OSError:
                pass
    return total


def download(model, progress_cb=None):
    """下载模型。progress_cb(done_bytes, total_bytes); total=0 表示未知(只报已下)。

    成功返回 True; 失败抛异常。
    """
    repo = model_repo(model)
    errors = []
    for ep in endpoints():
        total = _repo_total_bytes(repo, ep)
        state = {"done": False, "err": None}

        def _dl():
            try:
                _snapshot(repo, ep)
            except Exception as e:
                state["err"] = e
            state["done"] = True

        t = threading.Thread(target=_dl, daemon=True)
        t.start()
        while not state["done"]:
            if progress_cb:
                progress_cb(_downloaded_bytes(model), total)
            time.sleep(0.4)
        if not state["err"]:
            if progress_cb:
                got = _downloaded_bytes(model)
                progress_cb(got, total or got)
            return True
        errors.append(f"{ep}: {type(state['err']).__name__}")
        print(f"[模型] 下载源失败 {ep}: {str(state['err'])[:200]}")
    raise ModelDownloadError(user_message(model, errors))


def user_message(model, errors):
    """全部下载源失败时给用户看的一句话(双语; 只说他能做的事: 代理 / 手动放模型)。"""
    try:
        from i18n import t
    except Exception:          # 纯逻辑测试环境
        def t(s):
            return s
    tried = ", ".join(e.split("//")[-1].split(":")[0] for e in errors) or "-"
    return t("连不上模型下载源 (试过 {tried})。国内需要代理; 或把模型文件夹手动放到 "
             "{path} (含 model.bin)").format(
        tried=tried, path=f"%LOCALAPPDATA%\\BannerlordVoice\\models\\{model}\\")
