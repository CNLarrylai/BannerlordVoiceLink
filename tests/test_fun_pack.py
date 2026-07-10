# -*- coding: utf-8 -*-
"""整活词典测试 —— 激活/合并/隔离规则 + 示例包每条词必须正确路由 (秒级)。"""
import os
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import yaml  # noqa: E402

import dictionary  # noqa: E402
from matcher import Matcher  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(ROOT, "config", "settings.yaml"), encoding="utf-8") as f:
    settings = yaml.safe_load(f)

fails = 0


def check(name, cond, detail=""):
    global fails
    fails += not cond
    print(f"  {'✓' if cond else '✗✗✗'} {name} {detail}")


print("=== 激活/合并/隔离 ===")
_orig = dictionary.active_fun_pack

dictionary.active_fun_pack = lambda: None
base = dictionary.load_commands()
check("未激活: 整活词不进词典",
      "爸爸打我" not in base["orders"]["charge"]["aliases"])

dictionary.active_fun_pack = lambda: "示例整活包"
fun = dictionary.load_commands()
check("激活后: 爸爸打我 已合并进 charge",
      "爸爸打我" in fun["orders"]["charge"]["aliases"])
check("显示名不被整活词改变 (追加在尾部)",
      fun["orders"]["charge"]["aliases"][0]
      == base["orders"]["charge"]["aliases"][0])

dictionary.active_fun_pack = lambda: "不存在的包"
missing = dictionary.load_commands()
check("包不存在: 优雅忽略不崩",
      "爸爸打我" not in missing["orders"]["charge"]["aliases"])

print("\n=== 示例包逐条路由 (整活词必须解析到映射的指令) ===")
dictionary.active_fun_pack = lambda: "示例整活包"
cmds = dictionary.load_commands()
m = Matcher.from_config(cmds, settings["control"], lang="zh")
pack = dictionary.load_fun_pack("示例整活包")
for want_key, words in (pack.get("orders") or {}).items():
    for w in (words if isinstance(words, list) else words.get("aliases", [])):
        r = m.parse(w)
        got = r["order"]["name"] if r and r.get("order") else None
        check(f"「{w}」-> {want_key}", got == want_key, f"(实际 {got})")

print("\n=== 未激活时整活词不响应 (隔离性) ===")
dictionary.active_fun_pack = lambda: None
m0 = Matcher.from_config(dictionary.load_commands(), settings["control"],
                         lang="zh")
r = m0.parse("爸爸打我")
check("平时说「爸爸打我」不执行任何指令", r is None,
      f"(实际 {r and r['order']['name']})")

dictionary.active_fun_pack = _orig

if fails:
    print(f"\n❌ {fails} 个失败")
    sys.exit(1)
print("\n✓ 整活词典全部通过")
