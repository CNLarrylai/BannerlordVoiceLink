# -*- coding: utf-8 -*-
"""识别输出退化检测测试: 重复幻觉必须被抓, 正常指令绝不能误杀。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from stt import looks_degenerate  # noqa: E402

DEGENERATE = [
    "轻轻轻轻轻轻轻轻轻轻轻轻轻轻轻轻轻轻轻轻",
    "轻轻 轻轻 轻轻 轻轻 轻轻 轻轻",
    "一二一二一二一二一二",
    "哈哈哈哈哈哈哈",
    "no no no no no no",
    "chargechargechargecharge",
]
LEGIT = [
    "冲锋", "全军冲锋", "骑兵进攻弓箭手", "弓箭手自由射击",
    "轻骑兵冲锋",              # 含"轻"但正常
    "冲冲冲",                  # 战场喊话式, 3连不算退化
    "杀杀杀啊",
    "cavalry attack the nearest enemy",
    "shield wall", "fall back", "hold your fire",
    "全军排成一列", "骑射手散开", "上马",
]


def test_degenerate_caught():
    for s in DEGENERATE:
        assert looks_degenerate(s), f"漏抓: {s}"


def test_legit_never_killed():
    for s in LEGIT:
        assert not looks_degenerate(s), f"误杀: {s}"


def test_bundled_model_path_uses_repo_mapping():
    """打包版模型解析: 已下载到 HF 缓存的模型必须按名字交给 faster-whisper,
    仓库名走映射 (turbo 在 mobiuslabsgmbh 下, 不是 Systran) —— 曾写死 Systran,
    用户选 turbo 永远静默回退 small。"""
    import tempfile
    import stt
    import models
    with tempfile.TemporaryDirectory() as tmp:
        mei = os.path.join(tmp, "_internal")
        os.makedirs(os.path.join(mei, "models", "faster-whisper-small"))
        cache = os.path.join(tmp, "hub")
        snap = os.path.join(cache, "models--mobiuslabsgmbh--faster-whisper-large-v3-turbo",
                            "snapshots", "abc")
        os.makedirs(snap)
        with open(os.path.join(snap, "model.bin"), "wb") as f:
            f.truncate(21_000_000)      # 稀疏文件, 只要过 is_ready 的体积门槛
        old_cache, old_mei = models._CACHE, getattr(sys, "_MEIPASS", None)
        models._CACHE, sys._MEIPASS = cache, mei
        try:
            assert stt.bundled_model_path("large-v3-turbo") == "large-v3-turbo",                 "turbo 已在缓存却没按名字交给 faster-whisper"
            assert stt.bundled_model_path("small").endswith("faster-whisper-small")
            got = stt.bundled_model_path("medium")   # 没下载 -> 退回内置 small
            assert got.endswith("faster-whisper-small"), got
        finally:
            models._CACHE = old_cache
            if old_mei is None:
                del sys._MEIPASS
            else:
                sys._MEIPASS = old_mei


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
    print(f"\n{'❌ 有失败' if fails else '✓ 退化检测全部通过'}")
    sys.exit(1 if fails else 0)
