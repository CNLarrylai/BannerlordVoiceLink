# -*- coding: utf-8 -*-
"""伴侣模组探针 —— 战斗中直接问模组"现在场上是什么情况"。

模组的 socket 只在战斗中开着, 所以: 进一场战斗(不用暂停), 切出来跑本脚本。

用法:
  python tools/mod_probe.py                  # ping + 名册 + 当前选中 + 敌情
  python tools/mod_probe.py select cavalry   # 让模组选中骑兵(看游戏里高亮对不对)
  python tools/mod_probe.py raw "info"       # 发任意一行协议

排查"指令指挥错了人"就看名册那几行: 兵种后面的数字键才是游戏里真实的编队号。
玩家在"战斗部署 Order of Battle"里换过编队顺序时, 它和词典默认的 1/2/3/4 会不一样
—— 那就是 2026-09-25 查的 YouTube 用户 "archers 和 cavalry 反了" 的成因。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

import roster as rosters  # noqa: E402
from modlink import ModLink  # noqa: E402

CLASSES = ("infantry", "archers", "cavalry", "horse_archers")
CN = {"infantry": "步兵", "archers": "弓箭手",
      "cavalry": "骑兵", "horse_archers": "骑射"}
MIX = {"i": "步", "r": "弓", "c": "骑", "h": "骑射"}


def _mix_cn(mix):
    """i118,r2 -> 步118 弓2"""
    out = []
    for part in (mix or "").split(","):
        part = part.strip()
        if not part:
            continue
        out.append(MIX.get(part[:1], part[:1]) + part[1:])
    return " ".join(out) or "?"


def main():
    args = sys.argv[1:]
    ml = ModLink(timeout=1.0)
    if args and args[0] == "raw":
        print(ml._send(" ".join(args[1:])) or "(没有回应: 模组不在 / 不在战斗)")
        return 0
    if args and args[0] == "select":
        if len(args) < 2:
            print("用法: mod_probe.py select <infantry|archers|cavalry|horse_archers|all>")
            return 2
        print(f"select {args[1]} -> {ml.select(args[1])}")
        print(f"当前选中(数字键号): {ml.selected()}")
        return 0

    pong = ml.ping()
    print(f"ping      : {pong or '(没有回应)'}")
    if not pong:
        print("\n模组没应答。要么游戏没开, 要么不在战斗中(模组只在战斗里监听),"
              "\n要么模组没在启动器里勾上。")
        return 1
    if "battle=1" not in pong:
        print("\n模组在, 但当前不在战斗中 —— 进一场战斗再跑。")
        return 1

    r = rosters.Roster(ml, ttl=0)
    snap = r.snapshot()
    print("\n=== 编队名册 (数字键 = 游戏里真实的编队号) ===")
    if snap is None:
        print("  取不到名册(模组版本太老? 需要 v0.9.10+)")
        return 1
    for cls in CLASSES:
        info = snap.get(cls)
        if info is None:
            print(f"  {CN[cls]:<5} 没有这支队  → 喊到它时程序一个键都不会发"
                  f"(老版本会误按成全军令)")
        else:
            key, n, mix = info
            print(f"  {CN[cls]:<5} 数字键 {key}   {n} 人   成分 {_mix_cn(mix)}")
    default = {"infantry": "1", "archers": "2", "cavalry": "3", "horse_archers": "4"}
    odd = [CN[c] for c in CLASSES
           if snap.get(c) and snap[c][0] != default[c]]
    print("\n  " + ("⚠ 和默认布局不一样: " + "、".join(odd)
                    + " —— 你在“战斗部署”里换过编队顺序, 正是这种情况会让"
                      "老版本指挥错人。"
                    if odd else "✓ 就是默认布局 (步1 弓2 骑3 骑射4)"))
    print(f"\n当前选中  : {ml.selected()}")
    print(f"敌情      : {ml.info()}")
    print("  (敌情格式: 兵种槽号:人数:离你多少米)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
