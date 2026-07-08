# -*- coding: utf-8 -*-
"""CUDA 库检测/下载测试: 位置感知检测 + 下载解压逻辑(合成wheel, 不联网)。"""
import io
import os
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import cuda_libs  # noqa: E402


def test_is_ready_across_split_dirs():
    """cublas 和 cudnn 分处两个目录时(源码版真实情况)也应识别为就绪。"""
    a = tempfile.mkdtemp()
    b = tempfile.mkdtemp()
    open(os.path.join(a, "cublas64_12.dll"), "wb").write(b"x")
    open(os.path.join(b, "cudnn64_9.dll"), "wb").write(b"x")
    real = cuda_libs.search_dirs
    cuda_libs.search_dirs = lambda: [a, b]
    try:
        assert cuda_libs.is_ready()
        # 缺一个就不算就绪
        os.remove(os.path.join(b, "cudnn64_9.dll"))
        assert not _ready_no_system()
    finally:
        cuda_libs.search_dirs = real


def _ready_no_system():
    """屏蔽系统 load 兜底, 只看目录判定 (避免测试机真装了系统CUDA)。"""
    dirs = cuda_libs.search_dirs()
    return all(any(os.path.exists(os.path.join(d, dll)) for d in dirs)
               for dll in cuda_libs._REQUIRED)


def test_download_extracts_and_verifies(monkey=None):
    """download() 应从 wheel 里解出 DLL 到 cuda_dir 并校验齐全。"""
    d = tempfile.mkdtemp()
    # 造两个假 wheel: 各含一个标志 DLL (放在 nvidia/*/bin/ 下, 模拟真实结构)
    def fake_wheel(dll):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr(f"nvidia/x/bin/{dll}", b"\x00" * 4096)
            z.writestr("nvidia/x/__init__.py", b"")   # 非 dll, 应被忽略
        return buf.getvalue()

    wheels = {"cublas": fake_wheel("cublas64_12.dll"),
              "cudnn": fake_wheel("cudnn64_9.dll")}

    class FakeResp(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_wheel_url(pkg, ver):
        key = "cublas" if "cublas" in pkg else "cudnn"
        return f"http://x/{key}.whl", len(wheels[key])

    def fake_urlopen(url, timeout=0):
        key = "cublas" if "cublas" in url else "cudnn"
        return FakeResp(wheels[key])

    import urllib.request
    real_url, real_open, real_dir = (cuda_libs._wheel_url,
                                     urllib.request.urlopen, cuda_libs.cuda_dir)
    cuda_libs._wheel_url = fake_wheel_url
    urllib.request.urlopen = fake_urlopen
    cuda_libs.cuda_dir = lambda: d
    seen = []
    try:
        cuda_libs.download(lambda done, tot: seen.append((done, tot)))
        assert os.path.exists(os.path.join(d, "cublas64_12.dll"))
        assert os.path.exists(os.path.join(d, "cudnn64_9.dll"))
        assert not os.path.exists(os.path.join(d, "__init__.py"))  # 非dll不解
        # 进度回调: 最后一次应到 100%
        assert seen and seen[-1][0] == seen[-1][1]
    finally:
        cuda_libs._wheel_url = real_url
        urllib.request.urlopen = real_open
        cuda_libs.cuda_dir = real_dir


def test_download_missing_dll_raises():
    """wheel 里没有标志 DLL 时应报错(防静默残缺)。"""
    d = tempfile.mkdtemp()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("nvidia/x/bin/unrelated64.dll", b"x")
    data = buf.getvalue()

    class FakeResp(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False

    import urllib.request
    real_url, real_open, real_dir = (cuda_libs._wheel_url,
                                     urllib.request.urlopen, cuda_libs.cuda_dir)
    cuda_libs._wheel_url = lambda p, v: ("http://x/w.whl", len(data))
    urllib.request.urlopen = lambda u, timeout=0: FakeResp(data)
    cuda_libs.cuda_dir = lambda: d
    try:
        raised = False
        try:
            cuda_libs.download()
        except RuntimeError:
            raised = True
        assert raised, "缺标志DLL却没报错"
    finally:
        cuda_libs._wheel_url = real_url
        urllib.request.urlopen = real_open
        cuda_libs.cuda_dir = real_dir


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8")
        except Exception:
            pass
    fails = 0
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  ✓ {name}")
            except AssertionError as e:
                fails += 1
                print(f"  ✗✗✗ {name}: {e}")
    print(f"\n{'❌ 有失败' if fails else '✓ CUDA库检测/下载全部通过'}")
    sys.exit(1 if fails else 0)
