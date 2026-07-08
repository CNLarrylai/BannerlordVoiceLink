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
