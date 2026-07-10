# -*- coding: utf-8 -*-
"""指令复盘测试 —— 说法自动提取 + usage 新旧列兼容 (纯逻辑, 秒级)。"""
import csv
import os
import sys
import tempfile

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import yaml  # noqa: E402

import usage  # noqa: E402
from matcher import Matcher  # noqa: E402
from review import suggest_alias  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(ROOT, "config", "settings.yaml"), encoding="utf-8") as f:
    settings = yaml.safe_load(f)
with open(os.path.join(ROOT, "config", "commands.yaml"), encoding="utf-8") as f:
    commands = yaml.safe_load(f)
m = Matcher.from_config(commands, settings["control"], lang="zh")

fails = 0


def check(name, got, want):
    global fails
    ok = got == want
    fails += not ok
    print(f"  {'✓' if ok else '✗✗✗'} {name}: {got!r} (期望 {want!r})")


print("=== 说法自动提取 (suggest_alias) ===")
# 纠指令: 剔掉已匹配的兵种, 留下该学的动作词
check("全军出击→纠指令", suggest_alias(m, "全军出击", "order"), "出击")
check("骑兵回来→纠指令", suggest_alias(m, "骑兵回来", "order"), "回来")
# 纠兵种: 剔掉已匹配的指令, 留下该学的兵种词 ("宜宾"=步兵的错听, 实战日志)
check("宜宾回来→纠兵种", suggest_alias(m, "宜宾回来", "group"), "宜宾")
# 另一半没匹配上(整句未匹配): 不剔, 整句给用户手改
check("未匹配整句保留", suggest_alias(m, "呜哩哇啦", "order"), "呜哩哇啦")
# 标点被清洗
check("带标点", suggest_alias(m, "全军，出击。", "order"), "出击")
# 指向性指令的目标维: 剔兵种+指令, 只留动词后的目标词
check("骑兵进攻弓箭首→纠目标",
      suggest_alias(m, "骑兵进攻弓箭首", "target"), "弓箭首")
# 纠指令时目标也要被剔掉 (骑兵进攻弓箭手: 学"进攻"不能带上"弓箭手")
check("带目标句→纠指令",
      suggest_alias(m, "骑兵进攻弓箭手", "order"), "进攻")

print("\n=== usage.recent 新旧列兼容 ===")
tmp = tempfile.mkdtemp()
_orig = usage._path
usage._path = lambda: os.path.join(tmp, "usage.csv")
try:
    # 旧格式行(8列, 无 engine) + 新格式行(9列)
    with open(usage._path(), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(usage._FIELDS[:8])
        w.writerow(["2026-07-09 00:57:06", "zh", "ok", "all", "follow_me",
                    "keys", "0.10", "全军出击"])
    usage.record("zh", "ok", "all", "charge", "keys", 0.09, "全军出击", "快路")
    usage.record("zh", "ok", "cavalry", "charge", "mod", 0.10,
                 "骑兵进攻弓箭手", "快路", "archers")
    rows = usage.recent()
    check("行数", len(rows), 3)
    check("新行在前", rows[0]["order"], "charge")
    check("目标列记录", rows[0]["target"], "archers")
    check("无目标行补空", rows[1]["target"], "")
    check("新行引擎", rows[1]["engine"], "快路")
    check("旧行引擎补空", rows[2]["engine"], "")
    check("旧行文本", rows[2]["heard"], "全军出击")
finally:
    usage._path = _orig

if fails:
    print(f"\n❌ {fails} 个失败")
    sys.exit(1)
print("\n✓ 指令复盘逻辑全部通过")
