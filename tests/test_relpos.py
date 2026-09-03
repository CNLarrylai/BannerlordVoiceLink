# -*- coding: utf-8 -*-
"""相对站位/位置微调解析回归: 语法 A 去 B 的 C [D]; 既有指令绝不能被抢。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import yaml  # noqa: E402

import relpos  # noqa: E402
from matcher import Matcher  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(ROOT, "config", "settings.yaml"), encoding="utf-8") as f:
    CTRL = yaml.safe_load(f)["control"]
with open(os.path.join(ROOT, "config", "commands.yaml"), encoding="utf-8") as f:
    CMDS = yaml.safe_load(f)
M_ZH = Matcher.from_config(CMDS, CTRL)
M_EN = Matcher.from_config(CMDS, CTRL, lang="en")


def _r(text, lang="zh"):
    return relpos.parse(text, M_ZH if lang == "zh" else M_EN, lang)


def test_zh_relative_to_other():
    assert _r("骑兵去弓箭手右边") == {"group": "cavalry", "ward": "archers", "side": "right", "dist": 20}
    assert _r("步兵到骑射前面三十米") == {"group": "infantry", "ward": "horse_archers", "side": "front", "dist": 30}
    assert _r("骑兵站到弓箭手的后面") == {"group": "cavalry", "ward": "archers", "side": "back", "dist": 20}
    assert _r("骑射到骑兵左侧50米") == {"group": "horse_archers", "ward": "cavalry", "side": "left", "dist": 50}
    # 错听: 骑兵 -> 起兵(拼音兜底), 弓箭手 -> 功箭手
    assert _r("起兵去功箭手右边")["ward"] == "archers"


def test_zh_relative_to_self_needs_distance():
    assert _r("骑兵往右二十米") == {"group": "cavalry", "ward": None, "side": "right", "dist": 20}
    assert _r("步兵往后退五米") == {"group": "infantry", "ward": None, "side": "back", "dist": 5}
    assert _r("弓箭手向前移动十米")["side"] == "front"
    # 没距离 -> 不接, 归词典(后退/前进)
    assert _r("步兵往后退") is None
    assert _r("骑兵往右") is None


def test_zh_never_steals_existing_commands():
    for s in ("骑兵左队冲锋", "弓箭手去那", "弓箭手去那里", "步兵后退", "骑兵进攻弓箭手",
              "骑兵保护右翼", "骑兵右队跟我", "全军前进", "步兵往前压", "骑射右翼掩护",
              "骑兵绕到背后", "去右边", "往右五米"):        # 最后两句没说哪支队 -> 不接
        assert _r(s) is None, s


def test_en_relative():
    assert _r("Cavalry, go to the right of the archers", "en") == {"group": "cavalry", "ward": "archers", "side": "right", "dist": 20}
    assert _r("Infantry, move in front of the horse archers, 30 meters", "en") == {"group": "infantry", "ward": "horse_archers", "side": "front", "dist": 30}
    assert _r("Cavalry, get behind the archers", "en")["side"] == "back"
    assert _r("Cavalry, move 20 meters to the right", "en") == {"group": "cavalry", "ward": None, "side": "right", "dist": 20}
    assert _r("Infantry, move right by 15 meters", "en")["dist"] == 15
    assert _r("Archers, fall back 30 meters", "en") == {"group": "archers", "ward": None, "side": "back", "dist": 30}
    for s in ("Cavalry, fall back", "Archers, move here", "Cavalry left, charge",
              "Cavalry, protect the left flank", "Infantry, advance", "move right 20 meters"):
        assert _r(s, "en") is None, s


def test_describe():
    d = relpos.describe(_r("骑兵去弓箭手右边"), CMDS, "zh")
    assert "骑兵" in d and "弓箭手右边" in d and "20" in d
    d = relpos.describe(_r("Cavalry, move 20 meters to the right", "en"), CMDS, "en")
    assert "cavalry" in d and "right" in d


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
    print(f"\n{'❌ 有失败' if fails else '✓ 相对站位解析全部通过'}")
    sys.exit(1 if fails else 0)
