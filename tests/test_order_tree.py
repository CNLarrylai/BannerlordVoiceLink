# -*- coding: utf-8 -*-
"""指令树校验逻辑测试: 现有词典必须全部走得通; 坏键序必须被抓。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import yaml  # noqa: E402

from order_tree import load_tree, resolve, validate_commands  # noqa: E402
from paths import config_path  # noqa: E402


def _commands():
    with open(config_path("commands.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_all_current_commands_resolve():
    rows = validate_commands(load_tree(), _commands())
    bad = [r for r in rows if not r[2]]
    assert not bad, f"词典键位走不通指令树: {bad}"


def test_direct_key_resolves():
    ok, why = resolve(load_tree(), ["f8"])
    assert ok and "盾墙" in why, (ok, why)


def test_menu_sequence_resolves():
    ok, why = resolve(load_tree(), ["f1", "f3"])
    assert ok and "冲锋" in why, (ok, why)


def test_menu_without_item_fails():
    ok, why = resolve(load_tree(), ["f1"])
    assert not ok, why


def test_bogus_item_fails():
    ok, why = resolve(load_tree(), ["f2", "f9x"])
    assert not ok, why
    ok, why = resolve(load_tree(), ["f4", "f1"])   # f4 是直接键, 不能接子项
    assert not ok, why


def test_bad_group_key_flagged():
    tree = load_tree()
    cmds = {"groups": {"x": {"key": "7", "aliases": ["七队"]}}, "orders": {}}
    rows = validate_commands(tree, cmds)
    assert rows and not rows[0][2], rows


def test_en_meanings():
    ok, why = resolve(load_tree(), ["f2", "f6"], lang="en")
    assert ok and "Wedge" in why, (ok, why)


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
    print(f"\n{'❌ 有失败' if fails else '✓ 指令树校验全部通过'}")
    sys.exit(1 if fails else 0)
