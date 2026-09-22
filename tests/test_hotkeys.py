# -*- coding: utf-8 -*-
"""监听键"轻点"判定 (正确性门槛)。假 keyboard 库喂事件序列, 不碰真键盘。

锁住的实战场景(默认键左 Alt, 用户 2026-09-22 定):
  轻点一下 = 开关一次; Alt+Tab / 按住 Alt 看部队标记 / 长按自动连发 都不算;
  左右 Alt 扫描码相同, 按右 Alt 不能触发左 Alt。
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import hotkeys  # noqa: E402


class Ev:
    def __init__(self, t, code, name):
        self.event_type, self.scan_code, self.name = t, code, name


class FakeKB:
    CODES = {"left alt": (56,), "right alt": (56, 57400), "f12": (88,), "caps lock": (58,)}

    def __init__(self):
        self.hooks = []

    def key_to_scan_codes(self, k):
        return self.CODES[k]

    def hook(self, fn):
        self.hooks.append(fn)
        return fn

    def unhook(self, fn):
        self.hooks.remove(fn)

    def send(self, t, code, name):
        for h in list(self.hooks):
            h(Ev(t, code, name))


def _setup(key="left alt"):
    kb, hits = FakeKB(), []
    off = hotkeys.on_tap(key, lambda: hits.append(1), kb=kb)
    return kb, hits, off


def test_tap_toggles_once():
    kb, hits, _ = _setup()
    kb.send("down", 56, "alt"); kb.send("up", 56, "alt")
    assert hits == [1]
    kb.send("down", 56, "alt"); kb.send("up", 56, "alt")
    assert hits == [1, 1]


def test_alt_tab_is_not_a_tap():
    kb, hits, _ = _setup()
    kb.send("down", 56, "alt"); kb.send("down", 15, "tab"); kb.send("up", 15, "tab")
    kb.send("up", 56, "alt")
    assert hits == []


def test_holding_alt_is_not_a_tap():
    kb, hits, _ = _setup()
    old = hotkeys.TAP_MAX_SECS
    hotkeys.TAP_MAX_SECS = 0.05
    try:
        kb.send("down", 56, "alt")
        for _ in range(5):                       # 自动连发
            time.sleep(0.02)
            kb.send("down", 56, "alt")
        kb.send("up", 56, "alt")
        assert hits == [], "按住看部队标记后松开不该开关"
    finally:
        hotkeys.TAP_MAX_SECS = old


def test_autorepeat_within_tap_counts_once():
    kb, hits, _ = _setup("f12")
    kb.send("down", 88, "f12"); kb.send("down", 88, "f12"); kb.send("up", 88, "f12")
    assert hits == [1]


def test_right_alt_does_not_trigger_left_alt():
    kb, hits, _ = _setup()
    kb.send("down", 56, "right alt"); kb.send("up", 56, "right alt")
    assert hits == []


def test_unhook_stops_listening():
    kb, hits, off = _setup()
    off()
    kb.send("down", 56, "alt"); kb.send("up", 56, "alt")
    assert hits == []


def test_pretty_and_tk_mapping():
    assert hotkeys.pretty("left alt") == "Left Alt"
    assert hotkeys.pretty("f12") == "F12"
    assert hotkeys.pretty("caps lock") == "Caps Lock"
    assert hotkeys.from_tk("Alt_L") == "left alt"
    assert hotkeys.from_tk("Caps_Lock") == "caps lock"
    assert hotkeys.from_tk("F12") == "f12"
    assert hotkeys.from_tk("v") == "v"


def test_reject_game_keys_and_taken():
    assert hotkeys.reject_reason("f3")          # 指令菜单
    assert hotkeys.reject_reason("2")           # 编队
    assert hotkeys.reject_reason("w")           # 移动
    assert hotkeys.reject_reason("f10", taken=("f10", "f11"))
    assert hotkeys.reject_reason("left alt") is None
    assert hotkeys.reject_reason("caps lock") is None


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
    print(f"\n{'❌ 有失败' if fails else '✓ 监听键判定全部通过'}")
    sys.exit(1 if fails else 0)
