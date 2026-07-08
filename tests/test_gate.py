# -*- coding: utf-8 -*-
"""监听门逻辑测试: 手动开关 + 战斗自动门 的组合。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class _App:
    """只测门逻辑, 不构造整个 App(避免加载模型/音频)。"""
    from main import App
    _gate_open = App._gate_open
    _toggle_listen = App._toggle_listen

    def __init__(self, auto_gate):
        self.auto_battle_gate = auto_gate
        self.listen_on = True
        self.battle_on = not auto_gate
        self.toggle_key = "f12"

    def _idle(self, detail=""):
        pass


def test_no_gate_default_open():
    a = _App(auto_gate=False)
    assert a._gate_open()          # 不开自动门, 默认开着
    a._toggle_listen()
    assert not a._gate_open()      # 手动关 -> 关
    a._toggle_listen()
    assert a._gate_open()          # 再按 -> 开


def test_battle_gate_mutes_outside_battle():
    a = _App(auto_gate=True)
    assert not a._gate_open()      # 开自动门, 初始不在战斗 -> 静音
    a.battle_on = True             # 模组报进入战斗
    assert a._gate_open()          # -> 开
    a.battle_on = False
    assert not a._gate_open()      # 离开战斗 -> 静音


def test_manual_off_overrides_battle():
    a = _App(auto_gate=True)
    a.battle_on = True             # 在战斗中
    assert a._gate_open()
    a._toggle_listen()             # 但手动关掉
    assert not a._gate_open()      # 手动关优先, 静音


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
    print(f"\n{'❌ 有失败' if fails else '✓ 监听门逻辑全部通过'}")
    sys.exit(1 if fails else 0)
