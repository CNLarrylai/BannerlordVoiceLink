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


def manual_dir(model):
    """手动放模型 / ModelScope 下载落地的目录: <用户数据>\\models\\<模型名>\\。
    stt.bundled_model_path 最先看这里, 所以它和 HF 缓存一样算"就绪"。"""
    from paths import user_data_dir
    return os.path.join(user_data_dir(), "models", model)


def is_ready(model):
    """模型是否已完整下载 (手动目录或 HF 缓存里有像样的 model.bin)。"""
    if model in (None, "", "auto"):
        return True
    try:
        if os.path.getsize(os.path.join(manual_dir(model), "model.bin")) > 20_000_000:
            return True
    except Exception:
        pass
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


_UA = {"User-Agent": "BannerlordVoice/model-download"}


def _reachable(url, timeout=4):
    """4 秒内有任何 HTTP 回应就算通(国内连 hf.co 是长时间无响应, 不是快速拒绝;
    不先探一下, 每个源要卡到 hub 库自己超时, 用户以为死机)。"""
    import urllib.error
    import urllib.request
    try:
        urllib.request.urlopen(urllib.request.Request(url, method="HEAD", headers=_UA),
                               timeout=timeout)
        return True
    except urllib.error.HTTPError as e:
        return e.code < 500
    except Exception:
        return False


# ---------- ModelScope(魔搭, 阿里) —— 国内可达的备用源 ----------
# 2026-09-09 核实: 六个 faster-whisper 模型在魔搭上同名同文件(mobiuslabsgmbh/…turbo,
# Systran/…small 等)。它的文件接口是普通 HTTP, 不走 huggingface_hub, 所以直接下到
# manual_dir(model) —— 就是"手动放模型"目录, stt 侧零改动。
MODELSCOPE = "https://www.modelscope.cn"


def _ms_files(repo):
    import json
    import urllib.request
    u = f"{MODELSCOPE}/api/v1/models/{repo}/repo/files?Revision=master&Recursive=true"
    with urllib.request.urlopen(urllib.request.Request(u, headers=_UA), timeout=25) as r:
        d = json.load(r)
    files = [(f["Path"], int(f["Size"])) for f in d["Data"]["Files"]
             if f.get("Type") == "blob" and f["Path"] not in (".gitattributes", "README.md")]
    if not any(p == "model.bin" for p, _ in files):
        raise RuntimeError("modelscope repo has no model.bin")
    return files


def _ms_fetch(url, out, on_chunk):
    import urllib.request
    with urllib.request.urlopen(urllib.request.Request(url, headers=_UA), timeout=60) as r, \
            open(out + ".part", "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            on_chunk(len(chunk))
    os.replace(out + ".part", out)


def _modelscope_download(model, repo, progress_cb=None):
    dst = manual_dir(model)
    os.makedirs(dst, exist_ok=True)
    files = _ms_files(repo)
    total = sum(s for _, s in files)
    state = {"done": 0}

    def tick(n):
        state["done"] += n
        if progress_cb:
            progress_cb(state["done"], total)

    for path, size in files:
        out = os.path.join(dst, path)
        if os.path.isfile(out) and os.path.getsize(out) == size:
            tick(size)                       # 断点续传: 上次下完的整文件直接跳过
            continue
        os.makedirs(os.path.dirname(out), exist_ok=True)
        _ms_fetch(f"{MODELSCOPE}/models/{repo}/resolve/master/{path}", out, tick)
    if not os.path.isfile(os.path.join(dst, "model.bin")):
        raise RuntimeError("model.bin missing after modelscope download")
    return True


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
        if not _reachable(f"{ep}/api/models/{repo}"):
            errors.append(f"{ep}: unreachable")
            print(f"[模型] 下载源不可达(4s 无回应) {ep}")
            continue
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
    # HF 系全不通(典型: 国内无代理) -> 魔搭
    try:
        _modelscope_download(model, repo, progress_cb)
        print(f"[模型] 已从 ModelScope 下到 {manual_dir(model)}")
        return True
    except Exception as e:
        errors.append(f"{MODELSCOPE}: {type(e).__name__}")
        print(f"[模型] 下载源失败 {MODELSCOPE}: {str(e)[:200]}")
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
