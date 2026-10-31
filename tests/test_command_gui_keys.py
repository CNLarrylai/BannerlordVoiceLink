# -*- coding: utf-8 -*-
"""词典窗口改键回归: 改成纯数字键后再打开词典不许崩 (用户报 TypeError:
sequence item 0: expected str instance, int found, command_gui._fill_tree)。"""
import os
import shutil
import sys
import tempfile

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import yaml  # noqa: E402

import command_gui  # noqa: E402
import dictionary  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
fails = 0


def check(name, cond, detail=""):
    global fails
    fails += not cond
    print(f"  {'✓' if cond else '✗✗✗'} {name} {detail}")


tmp = tempfile.mkdtemp()
try:
    path = os.path.join(tmp, "commands.yaml")
    shutil.copy(os.path.join(ROOT, "config", "commands.yaml"), path)
    command_gui.COMMANDS = path

    print("=== 写入: 数字键带引号 ===")
    order = next(k for k, d in yaml.safe_load(open(path, encoding="utf-8"))["orders"].items()
                 if d.get("keys"))
    check("set_keys_in_yaml 成功", command_gui.set_keys_in_yaml("orders", order, ["f1", "2"]))
    raw = yaml.safe_load(open(path, encoding="utf-8"))
    check("写出后 YAML 读回仍是 str", raw["orders"][order]["keys"] == ["f1", "2"],
          str(raw["orders"][order]["keys"]))

    print("=== 读入: 旧版写坏的 int 键自愈 ===")
    text = open(path, encoding="utf-8").read().replace('[f1, "2"]', "[1, 2]")
    open(path, "w", encoding="utf-8").write(text)
    check("模拟坏文件确实是 int", yaml.safe_load(open(path, encoding="utf-8"))
          ["orders"][order]["keys"] == [1, 2])
    _cp = dictionary.config_path
    dictionary.config_path = lambda n: path if n == "commands.yaml" else _cp(n)
    cmds = dictionary.load_commands()
    dictionary.config_path = _cp
    keys = cmds["orders"][order]["keys"]
    check("load_commands 归一成 str", keys == ["1", "2"], str(keys))
    check("_fill_tree 的 join 不崩", "+".join(keys) == "1+2")
    check("所有指令/兵种键都是 str",
          all(isinstance(k, str) for d in cmds["orders"].values() for k in d.get("keys") or [])
          and all(isinstance(d.get(f), str) for d in cmds["groups"].values()
                  for f in ("key", "select") if d.get(f) is not None))
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print(f"\n{'✓ 全部通过' if not fails else f'✗ {fails} 项失败'}")
sys.exit(1 if fails else 0)
