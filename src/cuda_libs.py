# -*- coding: utf-8 -*-
"""CUDA 运行库 —— 检测 / 按需下载 (给有 N 卡但装的是 CPU 通用包的粉丝)。

CPU 通用包故意不含 CUDA 库(省 1.2GB)。这里让有 N 卡的用户在音频设置里
一键下载 cuBLAS + cuDNN 到 %LOCALAPPDATA%\\BannerlordVoice\\cuda\\,
之后 stt 把该目录加进 DLL 搜索路径, 自动走 GPU/turbo。

检测按"DLL 是否真的能被找到"判断(不是查 nvidia 这个 pip 包在不在)——
这样系统级 CUDA、下载来的库、源码版的 pip 库, 三种来源都能认出来。
"""
import glob
import io
import os
import sys
import zipfile

# 与源码版 .venv 对齐的版本 (和 ctranslate2 4.8 / faster-whisper 1.2 兼容)
_PKGS = [
    ("nvidia-cublas-cu12", "12.9.2.10"),
    ("nvidia-cudnn-cu12", "9.23.1.3"),
]
# 判定"CUDA 齐了"的标志性 DLL (这两个在, 整套就在)
_REQUIRED = ("cublas64_12.dll", "cudnn64_9.dll")

APP_DIRNAME = "BannerlordVoice"


def cuda_dir():
    d = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                     APP_DIRNAME, "cuda")
    return d


def _bundled_dirs():
    """源码版/未来 GPU 包里 pip 装的 nvidia 库路径 (可能有多个根)。"""
    dirs = []
    try:
        import nvidia
        for base in list(getattr(nvidia, "__path__", [])):
            for sub in ("cublas", "cudnn"):
                b = os.path.join(base, sub, "bin")
                if os.path.isdir(b):
                    dirs.append(b)
    except Exception:
        pass
    return dirs


def search_dirs():
    """所有可能放着 CUDA DLL 的目录 (下载目录 + pip 包目录)。"""
    dirs = [cuda_dir()] + _bundled_dirs()
    return [d for d in dirs if os.path.isdir(d)]


def add_to_search_path():
    """把候选目录加进 DLL 搜索路径 (启动时调一次)。"""
    for d in search_dirs():
        try:
            os.add_dll_directory(d)
            os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
        except Exception:
            pass


def is_ready():
    """这台机器上 CUDA 运行库找得到吗 (任一来源: 下载 / pip / 系统)。

    注意: cuBLAS 和 cuDNN 常分在不同目录 (源码版 .venv 里 cublas/bin 与
    cudnn/bin 是两个目录), 所以每个标志 DLL 只要在"任一"搜索目录里出现即可。
    """
    dirs = search_dirs()
    if all(any(os.path.exists(os.path.join(d, dll)) for d in dirs)
           for dll in _REQUIRED):
        return True
    # 系统级(CUDA Toolkit 在 PATH): 直接试 load
    try:
        import ctypes
        ctypes.WinDLL("cublas64_12.dll")
        ctypes.WinDLL("cudnn64_9.dll")
        return True
    except Exception:
        return False


def size_hint():
    return "≈ 1.2 GB"    # 语言中立, 中英 UI 直接嵌用


def _wheel_url(pkg, ver):
    import json
    import urllib.request
    # 版本化接口返回 "urls"(该版本的文件列表), 不是 "releases"
    d = json.load(urllib.request.urlopen(
        f"https://pypi.org/pypi/{pkg}/{ver}/json", timeout=30))
    for u in d.get("urls", []):
        if "win_amd64" in u["filename"] and u["filename"].endswith(".whl"):
            return u["url"], u["size"]
    raise RuntimeError(f"{pkg} {ver} 没有 win_amd64 wheel")


def download(progress_cb=None):
    """下载 cuBLAS+cuDNN wheel, 解出 DLL 到 cuda_dir。progress_cb(done, total)。

    成功返回 True; 失败抛异常。整个过程 https + 解压, 不需要 pip。
    """
    import urllib.request
    os.makedirs(cuda_dir(), exist_ok=True)
    plans = []
    total = 0
    for pkg, ver in _PKGS:
        url, size = _wheel_url(pkg, ver)
        plans.append((url, size))
        total += size

    done = 0
    for url, size in plans:
        buf = io.BytesIO()
        with urllib.request.urlopen(url, timeout=60) as r:
            while True:
                chunk = r.read(1 << 20)     # 1MB
                if not chunk:
                    break
                buf.write(chunk)
                done += len(chunk)
                if progress_cb:
                    progress_cb(done, total)
        # wheel 是 zip: 把里面所有 .dll 平铺解出到 cuda_dir
        buf.seek(0)
        with zipfile.ZipFile(buf) as z:
            for name in z.namelist():
                if name.lower().endswith(".dll"):
                    data = z.read(name)
                    out = os.path.join(cuda_dir(), os.path.basename(name))
                    with open(out, "wb") as f:
                        f.write(data)
    if progress_cb:
        progress_cb(total, total)
    # 落地校验: 标志性 DLL 必须都在
    missing = [d for d in _REQUIRED
               if not os.path.exists(os.path.join(cuda_dir(), d))]
    if missing:
        raise RuntimeError("下载后仍缺: " + ", ".join(missing))
    return True
