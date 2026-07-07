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

_SIZE = {
    "tiny": "约 75 MB", "base": "约 145 MB", "small": "约 480 MB",
    "medium": "约 1.5 GB", "large-v3": "约 3 GB", "large-v3-turbo": "约 1.6 GB",
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
    return _SIZE.get(model, "大小未知")


def _repo_total_bytes(repo):
    try:
        from huggingface_hub import HfApi
        info = HfApi().model_info(repo, files_metadata=True)
        return sum((s.size or 0) for s in info.siblings)
    except Exception:
        return 0


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
    total = _repo_total_bytes(repo)
    state = {"done": False, "err": None}

    def _dl():
        try:
            from huggingface_hub import snapshot_download
            snapshot_download(repo)
        except Exception as e:
            state["err"] = e
        state["done"] = True

    t = threading.Thread(target=_dl, daemon=True)
    t.start()
    while not state["done"]:
        if progress_cb:
            progress_cb(_downloaded_bytes(model), total)
        time.sleep(0.4)
    if state["err"]:
        raise state["err"]
    if progress_cb:
        got = _downloaded_bytes(model)
        progress_cb(got, total or got)
    return True
