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
        # 新签名: 返回候选URL列表(镜像优先, 官方兜底) + 大小
        key = "cublas" if "cublas" in pkg else "cudnn"
        return [f"http://mirror/{key}.whl", f"http://x/{key}.whl"], len(wheels[key])

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


def test_add_user_dir_recursive():
    """选中父目录时应递归找出含 DLL 的子目录并登记(cublas/cudnn 常分处)。"""
    root = tempfile.mkdtemp()
    cub = os.path.join(root, "nvidia", "cublas", "bin")
    cud = os.path.join(root, "nvidia", "cudnn", "bin")
    os.makedirs(cub)
    os.makedirs(cud)
    open(os.path.join(cub, "cublas64_12.dll"), "wb").write(b"x")
    open(os.path.join(cud, "cudnn64_9.dll"), "wb").write(b"x")
    tf = os.path.join(tempfile.mkdtemp(), "extra.txt")
    real_f, real_b, real_s = (cuda_libs._user_dirs_file,
                              cuda_libs._bundled_dirs, cuda_libs._system_cuda_dirs)
    cuda_libs._user_dirs_file = lambda: tf
    cuda_libs._bundled_dirs = lambda: []
    cuda_libs._system_cuda_dirs = lambda: []
    try:
        ok, hits = cuda_libs.add_user_dir(os.path.join(root, "nvidia"))
        assert ok and len(hits) == 2, (ok, hits)
        assert cuda_libs.is_ready()
        assert len(cuda_libs.user_extra_dirs()) == 2
        # 空目录: 未找到
        ok2, hits2 = cuda_libs.add_user_dir(tempfile.mkdtemp())
        assert not ok2 and not hits2
    finally:
        cuda_libs._user_dirs_file = real_f
        cuda_libs._bundled_dirs = real_b
        cuda_libs._system_cuda_dirs = real_s


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
    cuda_libs._wheel_url = lambda p, v: (["http://x/w.whl"], len(data))
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


def test_mirror_fallback_when_first_source_dies():
    """第一个源(国内镜像)断流时, 自动换下一个源重下这一包。

    国内粉丝下 1.2GB 常中途断 —— 这条回退是他们能不能装上 GPU 加速的关键。
    """
    import io
    import tempfile
    import urllib.request
    import zipfile

    d = tempfile.mkdtemp()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for dll in ("cublas64_12.dll", "cublasLt64_12.dll", "cudnn64_9.dll",
                    "cudnn_ops64_9.dll", "cudnn_engines_precompiled64_9.dll",
                    "cudnn_engines_runtime_compiled64_9.dll",
                    "cudnn_heuristic64_9.dll", "cudnn_graph64_9.dll",
                    "cudnn_adv64_9.dll", "cudnn_cnn64_9.dll"):
            z.writestr(f"nvidia/bin/{dll}", b"x" * 16)
    data = buf.getvalue()

    class FakeResp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    tried = []

    def flaky_urlopen(url, timeout=0):
        tried.append(url)
        if "mirror" in url:                 # 镜像"断流"
            raise OSError("connection reset")
        return FakeResp(data)

    real_url, real_open, real_dir, real_req = (
        cuda_libs._wheel_url, urllib.request.urlopen, cuda_libs.cuda_dir,
        cuda_libs._PKGS)
    cuda_libs._wheel_url = lambda p, v: (
        ["http://mirror/w.whl", "http://official/w.whl"], len(data))
    urllib.request.urlopen = flaky_urlopen
    cuda_libs.cuda_dir = lambda: d
    cuda_libs._PKGS = [("nvidia-cublas-cu12", "1.0")]
    try:
        cuda_libs.download()
        assert any("mirror" in u for u in tried), "没试镜像源"
        assert any("official" in u for u in tried), "镜像失败后没退到官方源"
        assert os.path.exists(os.path.join(d, "cublas64_12.dll")), "回退后没解出DLL"
    finally:
        cuda_libs._wheel_url = real_url
        urllib.request.urlopen = real_open
        cuda_libs.cuda_dir = real_dir
        cuda_libs._PKGS = real_req


def test_rank_by_speed_prefers_fastest_and_keeps_dead_last():
    """下载前并行测速: 快的排前, 探不通的排最后但不剔除。
    教训(2026-09-09): 固定镜像优先, 海外机器上阿里云 2.4MB/s vs 官方 95MB/s。"""
    import io
    import time
    import urllib.request

    class Resp(io.BytesIO):
        def __init__(self, delay):
            super().__init__(b"x" * (4 << 20))
            self.delay = delay

        def read(self, n=-1):
            time.sleep(self.delay)
            return super().read(n)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(url, timeout=0):
        if "dead" in url:
            raise OSError("refused")
        return Resp(0.05 if "slow" in url else 0.0)

    real_open = urllib.request.urlopen
    urllib.request.urlopen = fake_urlopen
    try:
        ranked = cuda_libs._rank_by_speed(
            ["http://slow/w.whl", "http://dead/w.whl", "http://fast/w.whl"], secs=0.3)
        assert ranked[0] == "http://fast/w.whl", ranked
        assert ranked[-1] == "http://dead/w.whl", ranked
        assert cuda_libs._rank_by_speed(["http://only/w.whl"]) == ["http://only/w.whl"]
    finally:
        urllib.request.urlopen = real_open


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
