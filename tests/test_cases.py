# -*- coding: utf-8 -*-
"""解析 tests/voice_test_cases.md —— 所有引擎共用的标准测试用例。

返回 [(说法, group_key或None, order_key或None, 类别)]。
类别: 'group' / 'order' / 'combo'。改用例只改那个 MD, 这里跟着变。
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
MD = os.path.join(HERE, "voice_test_cases.md")


def _rows(md_text, header):
    """取某个 '## <header>' 段落下的表格数据行 (跳过表头和分隔线)。"""
    out = []
    lines = md_text.splitlines()
    in_sec = False
    for line in lines:
        if line.startswith("## "):
            in_sec = header in line
            continue
        if not in_sec:
            continue
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if not cells or cells[0] in ("说法",) or set("".join(cells)) <= set("-: "):
            continue
        out.append(cells)
    return out


def load_cases(path=None):
    with open(path or MD, encoding="utf-8") as f:
        md = f.read()
    cases = []
    for phrase, g in _rows(md, "兵种 groups"):
        cases.append((phrase, g or None, None, "group"))
    for phrase, o in _rows(md, "指令 orders"):
        cases.append((phrase, None, o or None, "order"))
    for row in _rows(md, "组合 combos"):
        phrase, g, o = (row + ["", "", ""])[:3]
        cases.append((phrase, g or None, o or None, "combo"))
    return cases


if __name__ == "__main__":
    import sys
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8")
        except Exception:
            pass
    cs = load_cases()
    from collections import Counter
    by = Counter(c[3] for c in cs)
    print(f"共 {len(cs)} 条: {dict(by)}")
    for phrase, g, o, cat in cs:
        print(f"  [{cat:5}] 「{phrase}」 -> {g}/{o}")
