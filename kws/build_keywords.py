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


def main():
    import sherpa_onnx
    with open(os.path.join(ROOT, "config", "commands.yaml"), encoding="utf-8") as f:
        cmds = yaml.safe_load(f)

    lines = []
    skipped = []
    for sec, thresh in (("groups", GROUP_THRESH), ("orders", ORDER_THRESH)):
        for key, d in cmds[sec].items():
            for alias in d.get("aliases", []):
                try:
                    toks = sherpa_onnx.text2token(
                        [alias], tokens=TOKENS, tokens_type="ppinyin")[0]
                except Exception as e:
                    skipped.append((alias, str(e)[:40]))
                    continue
                if not toks:
                    skipped.append((alias, "空token"))
                    continue
                lines.append(f"{' '.join(toks)} :{SCORE} #{thresh} @{sec}:{key}")

    out = os.path.join(HERE, "keywords.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"✓ 写出 {len(lines)} 条关键词 -> {out}")
    if skipped:
        print(f"跳过 {len(skipped)} 条:", skipped[:5])


if __name__ == "__main__":
    main()
