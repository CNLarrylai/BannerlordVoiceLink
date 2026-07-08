# -*- coding: utf-8 -*-
"""校准与个人词典测试: 合并加载 / 错听建议规则(宁缺勿滥) / 出题构建。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import yaml  # noqa: E402

import dictionary  # noqa: E402
from calibrate import build_items, judge, suggest_aliases  # noqa: E402
from matcher import Matcher  # noqa: E402
from paths import config_path  # noqa: E402


def _matcher(lang="zh"):
    cmds = dictionary.load_commands()
    with open(config_path("settings.yaml"), encoding="utf-8") as f:
        ctrl = yaml.safe_load(f)["control"]
    return Matcher.from_config(cmds, ctrl, lang=lang), cmds


def test_merge_user_aliases(tmp_marker=None):
    base = dictionary.load_commands()
    # 合并逻辑纯函数化验证: 手工造一份 user 数据
    user = {"orders": {"charge": {"aliases": ["测试专用冲一个"]}}}
    real_load_user = dictionary.load_user
    dictionary.load_user = lambda: user
    try:
        merged = dictionary.load_commands()
        assert "测试专用冲一个" in merged["orders"]["charge"]["aliases"]
        # 基础词典本身不被污染重复
        assert merged["orders"]["charge"]["aliases"].count("冲锋") == 1
    finally:
        dictionary.load_user = real_load_user
    assert "测试专用冲一个" not in base["orders"]["charge"]["aliases"]


def test_build_items_bilingual():
    _, cmds = _matcher()
    zh = build_items(cmds, "zh")
    en = build_items(cmds, "en")
    assert len(zh) == len(en) and len(zh) > 15
    assert any(i["say"] == "冲锋" for i in zh)
    assert any(i["say"] == "charge" for i in en)
    combo = [i for i in zh if i["combo"]]
    assert combo and combo[0]["group"] and combo[0]["order"]


def test_judge():
    m, cmds = _matcher()
    items = {(i["group"], i["order"]): i for i in build_items(cmds, "zh")}
    assert judge(m, items[(None, "charge")], "冲锋")
    assert not judge(m, items[(None, "charge")], "撤退")
    assert judge(m, items[("all", "charge")], "全军冲锋")
    assert not judge(m, items[("all", "charge")], "步兵冲锋")  # 兵种不对


def test_suggest_rules():
    m, _ = _matcher()
    # 前置: "利己"(liji) 现在匹配不到任何指令(音近立定但非同音, 拼音兜底接不住)
    assert m.parse("利己") is None
    # 而"冲缝"是冲锋的同音字, 拼音匹配已经接得住 -> 不需要也不应该学
    assert m.parse("冲缝") is not None
    attempts = [
        # 该学: 单词题, 没匹配上, 拼音相近(liji~liding), 且加了不撞
        {"group": None, "order": "halt", "say": "立定", "combo": False,
         "heard": "利己", "ok": False},
        # 不学: 同音错听拼音层已能匹配(matcher.parse 非 None)
        {"group": None, "order": "charge", "say": "冲锋", "combo": False,
         "heard": "冲缝", "ok": False},
        # 不学: 已经匹配对了
        {"group": None, "order": "halt", "say": "立定", "combo": False,
         "heard": "立定", "ok": True},
        # 不学: 听到的能匹配到别的指令(加了会撞)
        {"group": None, "order": "charge", "say": "冲锋", "combo": False,
         "heard": "撤退", "ok": False},
        # 不学: 和目标差太远(环境噪音)
        {"group": None, "order": "line", "say": "线阵", "combo": False,
         "heard": "今天天气不错", "ok": False},
        # 不学: 组合句不做别名学习
        {"group": "all", "order": "charge", "say": "全军冲锋", "combo": True,
         "heard": "全军冲缝", "ok": False},
    ]
    sugs = suggest_aliases(attempts, m, "zh")
    assert len(sugs) == 1, sugs
    assert sugs[0]["alias"] == "利己" and sugs[0]["key"] == "halt"


def test_bare_charge_not_hijacked():
    # 回归锁定: 光杆"冲锋"曾被 mount_toggle 的"上马冲锋"和 cavalry 的"冲锋骑"
    # 抢走(短文本滑进长别名满分, 同分比长度错赢)。
    m, _ = _matcher()
    tr = m.explain("冲锋")
    assert tr["order"]["name"] == "charge", tr["order"]
    assert not (tr["group"] and tr["group"]["pass"]), tr["group"]
    r = m.parse("冲锋")
    assert r and r["order"]["keys"] == ["f1", "f3"]


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
    print(f"\n{'❌ 有失败' if fails else '✓ 校准/个人词典全部通过'}")
    sys.exit(1 if fails else 0)
