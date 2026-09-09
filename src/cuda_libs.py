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

from i18n import t

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


def _user_dirs_file():
    return os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                        APP_DIRNAME, "cuda_extra_dirs.txt")


def user_extra_dirs():
    """用户"指定文件夹"手动登记的 CUDA 库目录 (已有库、免下载)。"""
    p = _user_dirs_file()
    if not os.path.exists(p):
        return []
    try:
        with open(p, encoding="utf-8") as f:
            return [ln.strip() for ln in f if ln.strip() and os.path.isdir(ln.strip())]
    except Exception:
        return []


def add_user_dir(folder):
    """在 folder 里(含子目录)找 CUDA 库, 找到就登记。

    返回 (是否齐全, [登记的目录])。用户可能选中父目录(如 .venv 的 nvidia),
    cuBLAS/cuDNN 分处 cublas/bin 与 cudnn/bin —— 递归找出真正含 DLL 的目录。
    """
    hits = []
    for dp, _dirs, files in os.walk(folder):
        low = {f.lower() for f in files}
        if any(dll in low for dll in _REQUIRED):
            hits.append(dp)
        if dp.count(os.sep) - folder.count(os.sep) > 4:   # 限深, 别扫太久
            _dirs[:] = []
    if not hits:
        return False, []
    existing = set(user_extra_dirs())
    existing.update(hits)
    os.makedirs(os.path.dirname(_user_dirs_file()), exist_ok=True)
    with open(_user_dirs_file(), "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(existing)) + "\n")
    # 齐不齐: 登记后两个标志 DLL 是否都能在某个登记目录里找到
    all_dirs = list(existing)
    ok = all(any(os.path.exists(os.path.join(d, dll)) for d in all_dirs)
             for dll in _REQUIRED)
    return ok, hits


def _system_cuda_dirs():
    """系统 CUDA Toolkit 的 bin (装了 Toolkit 的人自动认到, 免下载)。"""
    dirs = []
    cp = os.environ.get("CUDA_PATH")
    if cp and os.path.isdir(os.path.join(cp, "bin")):
        dirs.append(os.path.join(cp, "bin"))
    root = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"),
                        "NVIDIA GPU Computing Toolkit", "CUDA")
    if os.path.isdir(root):
        for v in os.listdir(root):
            b = os.path.join(root, v, "bin")
            if os.path.isdir(b):
                dirs.append(b)
    return dirs


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
    """所有可能放着 CUDA DLL 的目录 (下载 / pip包 / 用户指定 / 系统Toolkit)。"""
    dirs = ([cuda_dir()] + user_extra_dirs() + _bundled_dirs()
            + _system_cuda_dirs())
    seen, out = set(), []
    for d in dirs:
        if d and os.path.isdir(d) and d not in seen:
            seen.add(d)
            out.append(d)
    return out


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


# PyPI JSON 索引源: 国内镜像优先(pypi.org 在国内慢到下不完 1.2GB)。
# 实测(2026-08): 清华镜像不提供 /pypi/<pkg>/<ver>/json 接口(404), 已剔除;
# 阿里云可用。海外用户访问阿里云也通, 失败自动退到官方, 两边都不吃亏。
_INDEXES = [
    "https://mirrors.aliyun.com/pypi",          # 阿里云(国内快)
    "https://pypi.org/pypi",                    # 官方(兜底)
]

# wheel 直链的镜像替换: 官方文件站 -> 国内文件镜像(路径结构一致)。
# 清华文件站 2026-09 对 wheel 直链返回 403, 已剔除。候选顺序不重要 —— 下载前
# _rank_by_speed 并行实测两秒, 谁快用谁(2026-09-09 实测: 海外/挂梯子的机器上阿里云
# 只有 2.4 MB/s, 官方 95 MB/s, 而原先固定镜像优先, 1.2GB 要下 8 分钟)。
_FILE_MIRRORS = [
    "https://mirrors.aliyun.com/pypi/web",
]


def _rank_by_speed(cands, secs=2.0, cap=16 << 20):
    """并行探测每个候选 URL 的实际吞吐(读 secs 秒或 cap 字节), 按快慢排序返回。
    探不通的排最后但不剔除(探测时抖动不代表下载时也失败)。单候选直接返回。"""
    if len(cands) < 2:
        return list(cands)
    import threading
    import time
    import urllib.request
    speed = {u: -1.0 for u in cands}

    def probe(u):
        t0 = time.time()
        n = 0
        try:
            with urllib.request.urlopen(u, timeout=8) as r:
                while time.time() - t0 < secs and n < cap:
                    chunk = r.read(1 << 18)
                    if not chunk:
                        break
                    n += len(chunk)
            speed[u] = n / max(time.time() - t0, 1e-3)
        except Exception:
            speed[u] = -1.0

    threads = [threading.Thread(target=probe, args=(u,), daemon=True) for u in cands]
    for th in threads:
        th.start()
    for th in threads:
        th.join(secs + 10)
    ranked = sorted(cands, key=lambda u: -speed[u])
    print("[CUDA] 下载源测速: " + ", ".join(
        f"{u.split('/')[2]} {speed[u]/1e6:.1f}MB/s" if speed[u] >= 0 else f"{u.split('/')[2]} 不通"
        for u in ranked))
    return ranked


def _mirror_of(url, host):
    """把 files.pythonhosted.org 直链换成某个国内文件镜像。"""
    pref = "https://files.pythonhosted.org"
    return host + url[len(pref):] if url.startswith(pref) else None


def _wheel_url(pkg, ver):
    """返回 [(候选下载URL, 大小)] —— 第一个是最快的源, 失败可依次退。"""
    import json
    import urllib.request
    last_err = None
    for index in _INDEXES:
        try:
            # 版本化接口返回 "urls"(该版本的文件列表), 不是 "releases"
            api = f"{index}/{pkg}/{ver}/json"
            d = json.load(urllib.request.urlopen(api, timeout=15))
            for u in d.get("urls", []):
                if "win_amd64" in u["filename"] and u["filename"].endswith(".whl"):
                    # 国内文件镜像优先, 官方直链兜底(某源断流就换下一个)
                    cands = []
                    for host in _FILE_MIRRORS:
                        m = _mirror_of(u["url"], host)
                        if m and m not in cands:
                            cands.append(m)
                    cands.append(u["url"])
                    return cands, u["size"]
        except Exception as e:
            last_err = e
            continue
    raise RuntimeError(t("{pkg} {ver} 找不到 win_amd64 wheel: {err}").format(
        pkg=pkg, ver=ver, err=last_err))


def download(progress_cb=None):
    """下载 cuBLAS+cuDNN wheel, 解出 DLL 到 cuda_dir。progress_cb(done, total)。

    成功返回 True; 失败抛异常。整个过程 https + 解压, 不需要 pip。
    """
    import urllib.request
    os.makedirs(cuda_dir(), exist_ok=True)
    plans = []
    total = 0
    for pkg, ver in _PKGS:
        cands, size = _wheel_url(pkg, ver)
        plans.append((cands, size))
        total += size

    done = 0
    for cands, size in plans:
        base_done = done
        buf = None
        last_err = None
        for url in _rank_by_speed(cands):   # 先测速排序; 某源断流就换下一个重下这一包
            try:
                done = base_done
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
                break
            except Exception as e:
                last_err = e
                buf = None
                continue
        if buf is None:
            raise RuntimeError(t("所有下载源都失败了: {err}").format(err=last_err))
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
        raise RuntimeError(t("下载后仍缺: {missing}").format(missing=", ".join(missing)))
    return True
