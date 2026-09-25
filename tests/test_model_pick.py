# -*- coding: utf-8 -*-
"""模型挑选测试 —— 打包版"包里只带 base"时 auto 必须落在 base 上。

背景 (0.9.11 瘦身): 包里不再内置 small(464MB), 只内置 base(142MB)。
两个必须锁死的行为:
  ① auto 在无卡机器上不能指向一个"要联网下 464MB"的模型, 否则新用户首启
     就卡在下载(国内更惨)。small 下过才用它。
  ② 判断"要不要下载"必须用 stt.model_available 而不是 models.is_ready ——
     后者看不见**内置进包**的模型, 打包版会把已内置的 base 再下一遍
     (新用户白下 145MB, listen.py 首启踩过)。

CLAUDE.md 的教训: 凡"模型解析"必须用假 _MEIPASS 测, 不能只在源码形态下测。
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import stt  # noqa: E402


def _fake_package(*bundled):
    """造一个假的 PyInstaller 解包目录, 里面只有指定的几个模型。"""
    d = tempfile.mkdtemp()
    for m in bundled:
        p = os.path.join(d, "models", f"faster-whisper-{m}")
        os.makedirs(p)
        open(os.path.join(p, "model.bin"), "wb").close()
    return d


class _Env:
    """临时把进程伪装成打包版, 并控制"缓存里有什么"。"""
    def __init__(self, meipass, cached=()):
        self.meipass = meipass
        self.cached = set(cached)

    def __enter__(self):
        import models
        self._old_mei = getattr(sys, "_MEIPASS", None)
        sys._MEIPASS = self.meipass
        self._old_ready = models.is_ready
        models.is_ready = lambda m: m in self.cached
        # 手动放模型的目录不能干扰: 指到一个空目录
        import paths
        self._old_udir = paths.user_data_dir
        empty = tempfile.mkdtemp()
        paths.user_data_dir = lambda: empty
        return self

    def __exit__(self, *a):
        import models
        import paths
        models.is_ready = self._old_ready
        paths.user_data_dir = self._old_udir
        if self._old_mei is None:
            del sys._MEIPASS
        else:
            sys._MEIPASS = self._old_mei


def test_auto_on_cpu_uses_bundled_base_when_small_absent():
    with _Env(_fake_package("base")):
        model, device, _c, _hw = stt.resolve_stt_config(
            {"model": "auto", "device": "cpu"})
        assert device == "cpu"
        assert model == "base", model      # 绝不能是 small(要联网下 464MB)


def test_auto_on_cpu_prefers_small_once_downloaded():
    with _Env(_fake_package("base"), cached=["small"]):
        model, _d, _c, _hw = stt.resolve_stt_config(
            {"model": "auto", "device": "cpu"})
        assert model == "small", model     # 下过就用更准的


def test_auto_on_gpu_still_turbo():
    with _Env(_fake_package("base")):
        model, _d, _c, _hw = stt.resolve_stt_config(
            {"model": "auto", "device": "cuda"})
        assert model == "large-v3-turbo", model


def test_bundled_base_is_available_so_never_redownloaded():
    """listen.py 的下载判断走这个函数 —— 内置的 base 必须算"已有"。"""
    with _Env(_fake_package("base")):
        assert stt.model_available("base") is True
        assert stt.model_available("small") is False


def test_cached_model_counts_as_available():
    with _Env(_fake_package("base"), cached=["large-v3-turbo"]):
        assert stt.model_available("large-v3-turbo") is True


def test_bundled_path_falls_back_to_base_for_unavailable_choice():
    """用户显式选了下不动的 large-v3: 退回内置 base, 不崩。"""
    with _Env(_fake_package("base")):
        p = stt.bundled_model_path("large-v3")
        assert p.endswith("faster-whisper-base"), p


def test_explicit_small_still_honored_if_cached():
    with _Env(_fake_package("base"), cached=["small"]):
        model, _d, _c, _hw = stt.resolve_stt_config(
            {"model": "small", "device": "cpu"})
        assert model == "small"
        assert stt.bundled_model_path("small") == "small"   # 交给 faster-whisper 解析


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
    print(f"\n{'❌ 有失败' if fails else '✓ 模型挑选全部通过'}")
    sys.exit(1 if fails else 0)
