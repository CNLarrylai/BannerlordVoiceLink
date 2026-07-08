# -*- coding: utf-8 -*-
"""从 commands.yaml 生成 sherpa-onnx KWS 词表 (keywords.txt)。

每条中文别名 -> 拼音token序列 + 标签(命令key)。KWS 检测到任一别名的读音,
就报出对应命令。非对称阈值直接落到每条的 #threshold:
  兵种(叫法少、要好触发) 阈值低; 指令(密、防误触) 阈值略高。
"""
import os
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

MODEL = os.path.join(HERE, "models",
                     "sherpa-onnx-kws-zipformer-zh-en-3M-2025-12-20")
TOKENS = os.path.join(MODEL, "tokens.txt")

# 非对称阈值(可调): 兵种松、指令严 —— 对应你早就定的策略
GROUP_THRESH = 0.20
ORDER_THRESH = 0.25
SCORE = 1.5


MIN_LEN = 2   # KWS 别名至少 2 字: 单字("放/杀/冲")音短易误触发, 只适合模糊匹配


def _curate(cmds):
    """挑出适合 KWS 的别名。

    主别名(每条第一个=命令本名, 如"骑兵""自由射击")永远保留 —— 它们是核心
    命令词, 哪怕是别的命令的子串(骑兵⊂弓骑兵)也不能丢。
    次要别名: 去单字("放/杀") + 去"是别的命令别名子串"的(射击⊂停止射击, 会误触发)。
    """
    entries = []
    primaries = set()          # (sec,key) 的主别名文本
    all_alias = []             # (alias, sec, key, is_primary)
    for sec in ("groups", "orders"):
        for key, d in cmds[sec].items():
            al = d.get("aliases", [])
            if al:
                primaries.add(al[0])
            for i, a in enumerate(al):
                all_alias.append((a, sec, key, i == 0))
    for a, sec, key, is_primary in all_alias:
        if is_primary:
            entries.append((sec, key, a))
            continue
        if len(a) < MIN_LEN:
            continue
        # 次要别名: 是别的命令某别名的真子串 => 丢(念长词时会误触发短的)
        conflict = any(a != b and a in b and (bsec, bkey) != (sec, key)
                       for b, bsec, bkey, _ in all_alias)
        if conflict:
            continue
        entries.append((sec, key, a))
    return entries


def main():
    import sherpa_onnx
    with open(os.path.join(ROOT, "config", "commands.yaml"), encoding="utf-8") as f:
        cmds = yaml.safe_load(f)

    lines = []
    skipped = []
    thresh_of = {"groups": GROUP_THRESH, "orders": ORDER_THRESH}
    for sec, key, alias in _curate(cmds):
        try:
            toks = sherpa_onnx.text2token(
                [alias], tokens=TOKENS, tokens_type="ppinyin")[0]
        except Exception as e:
            skipped.append((alias, str(e)[:40]))
            continue
        if not toks:
            skipped.append((alias, "空token"))
            continue
        lines.append(f"{' '.join(toks)} :{SCORE} #{thresh_of[sec]} @{sec}:{key}")

    out = os.path.join(HERE, "keywords.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"✓ 写出 {len(lines)} 条关键词 -> {out}")
    if skipped:
        print(f"跳过 {len(skipped)} 条:", skipped[:5])


if __name__ == "__main__":
    main()
