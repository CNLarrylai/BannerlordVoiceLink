# -*- coding: utf-8 -*-
"""把 docs/CHANGELOG.md 最上面那个版本渲染成创意工坊 Change Notes, 写进 item.vdf。

用法:
  .venv\\Scripts\\python tools\\release_notes.py            # 最新版本 -> item.vdf
  .venv\\Scripts\\python tools\\release_notes.py --version 0.9.6
  .venv\\Scripts\\python tools\\release_notes.py --preview  # 只打印, 不写

CHANGELOG 约定 (见文件头): "## <版本> — <日期>" 起一节, 下面 "### 中文" / "### English"
两段, 每段是 "- " 开头的条目。渲染成 BBCode(工坊 Change Notes 支持), 换行写成
字面 \\n —— SteamCMD 的 workshop_build_item 会把它还原成真换行。
"""
import os
import re
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHANGELOG = os.path.join(ROOT, "docs", "CHANGELOG.md")
ITEM_VDF = os.path.join(ROOT, "tools", "steamcmd", "item.vdf")

_SECTION = re.compile(r"^## (\S+)\s+[—-]+\s+(\S+)\s*$", re.M)


def parse(md):
    """-> [{"version", "date", "zh": [...], "en": [...]}], 文件顺序。"""
    heads = list(_SECTION.finditer(md))
    out = []
    for i, h in enumerate(heads):
        body = md[h.end(): heads[i + 1].start() if i + 1 < len(heads) else len(md)]
        entry = {"version": h.group(1), "date": h.group(2), "zh": [], "en": []}
        cur = None
        for line in body.splitlines():
            if line.startswith("### "):
                cur = "en" if "english" in line.lower() else "zh"
            elif line.startswith("- ") and cur:
                entry[cur].append(line[2:].strip())
        out.append(entry)
    return out


def _md_inline_to_bbcode(s):
    s = re.sub(r"\*\*(.+?)\*\*", r"[b]\1[/b]", s)
    s = re.sub(r"`(.+?)`", r"\1", s)
    return s.replace('"', "'")     # VDF 字符串里不能有双引号


def render(entry):
    lines = [f"[h2]v{entry['version']}  ({entry['date']})[/h2]"]
    for tag, key in (("中文", "zh"), ("English", "en")):
        if not entry[key]:
            continue
        lines.append(f"[h3]{tag}[/h3]")
        lines.append("[list]")
        lines += [f"[*]{_md_inline_to_bbcode(x)}" for x in entry[key]]
        lines.append("[/list]")
    return "\\n".join(lines)


def write_vdf(note):
    with open(ITEM_VDF, encoding="utf-8") as f:
        vdf = f.read()
    new, n = re.subn(r'"changenote"\s+"[^"]*"',
                     lambda m: '"changenote"\t\t"' + note + '"', vdf)
    if n != 1:
        raise SystemExit("item.vdf 里没找到唯一的 changenote 字段")
    with open(ITEM_VDF, "w", encoding="utf-8", newline="\n") as f:
        f.write(new)


def main():
    with open(CHANGELOG, encoding="utf-8") as f:
        entries = parse(f.read())
    if not entries:
        raise SystemExit("CHANGELOG.md 里没有 '## 版本 — 日期' 节")
    want = None
    if "--version" in sys.argv:
        want = sys.argv[sys.argv.index("--version") + 1]
    entry = next((e for e in entries if want is None or e["version"] == want), None)
    if entry is None:
        raise SystemExit(f"CHANGELOG.md 里没有版本 {want}")
    note = render(entry)
    print(note.replace("\\n", "\n"))
    if "--preview" in sys.argv:
        return
    write_vdf(note)
    print(f"\n已写入 {ITEM_VDF} (v{entry['version']}, 中文 {len(entry['zh'])} 条 / "
          f"English {len(entry['en'])} 条)")


if __name__ == "__main__":
    main()
