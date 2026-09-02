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


def test_full_drill_covers_every_order():
    """完整题库: 词典里每条指令都出现且中英都能出题; 护弓带目标, 判定要看目标。"""
    from calibrate import build_full_drill, load_drill
    cmds = dictionary.load_commands()
    drill = build_full_drill(cmds)
    orders_in = {e[1] for e in drill if e[1]}
    missing = set(cmds["orders"]) - orders_in
    assert not missing, f"完整题库漏了指令: {missing}"
    for lang in ("zh", "en"):
        items = build_items(cmds, lang, drill)
        assert len(items) >= len(cmds["orders"]) + 5, lang
        assert all("?" not in i["say"] for i in items), lang
    d2, src = load_drill(cmds, "zh", "full")
    assert src == "full" and d2 == drill
    # 护弓: 出题句自带目标, 念对目标才算过
    zh = {(i["group"], i["order"]): i for i in build_items(cmds, "zh", drill)}
    prot = zh[("cavalry", "protect")]
    assert prot["target"] == "archers" and prot["say"] == "骑兵保护弓箭手", prot
    with open(config_path("settings.yaml"), encoding="utf-8") as f:
        m = Matcher.from_config(cmds, yaml.safe_load(f)["control"])
    assert judge(m, prot, "骑兵保护弓箭手")
    assert not judge(m, prot, "骑兵保护")
    assert judge(m, zh[("horse_archers", "skirmish")], "骑射游击")
    assert judge(m, zh[("cavalry_left", "charge")], "骑兵左队冲锋")


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


def test_usage_top_commands():
    import tempfile
    import usage
    d = tempfile.mkdtemp(prefix="usage_")
    real = usage._path
    usage._path = lambda: os.path.join(d, "usage.csv")
    try:
        # 不足 min_rows -> None (退回默认题库)
        for _ in range(10):
            usage.record("zh", "ok", "all", "charge", "keys", 0.5, "全军冲锋")
        assert usage.top_commands("zh", n=20, min_rows=40) is None
        # 攒够后: 按频次排序, 去重, miss/他语言不计入
        for _ in range(35):
            usage.record("zh", "ok", "cavalry", "advance", "mod", 0.4, "x")
        for _ in range(5):
            usage.record("zh", "ok", None, "halt", "keys", 0.3, "立定")
        for _ in range(9):
            usage.record("zh", "miss", None, None, "", 0.3, "聊天")
        for _ in range(50):
            usage.record("en", "ok", "all", "retreat", "keys", 0.3, "retreat")
        top = usage.top_commands("zh", n=2, min_rows=40)
        assert top is not None and len(top) == 2
        assert top[0][0] == ("cavalry", "advance") and top[0][1] == 35
        assert top[1][0] == ("all", "charge")
    finally:
        usage._path = real


def test_load_drill_sources():
    """快速模式的三级题源(完整模式不读这些, 见 test_full_drill_covers_every_order)。"""
    import usage
    from calibrate import load_drill
    _, cmds = _matcher()
    real = usage.top_commands
    # 无使用数据 -> 默认题库(calibration.yaml)
    usage.top_commands = lambda lang, n=20, min_rows=40: None
    try:
        drill, src = load_drill(cmds, "zh", "quick")
        assert src == "default" and len(drill) > 15
        assert ("all", "charge") in drill
        # 有使用数据 -> 你的 top 清单(过滤掉词典里不存在的键)
        usage.top_commands = lambda lang, n=20, min_rows=40: [
            (("cavalry", "advance"), 35), ((None, "halt"), 9),
            (("ghost_group", "charge"), 5)]
        drill, src = load_drill(cmds, "zh", "quick")
        assert src == "usage"
        assert drill == [("cavalry", "advance"), (None, "halt")]
    finally:
        usage.top_commands = real


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
