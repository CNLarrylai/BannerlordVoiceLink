# -*- coding: utf-8 -*-
"""使用统计 —— 每条指令直写 usage.csv, 数据驱动校准题库/词典优化。

设计原因: 曾靠解析黑窗日志统计, 结果"黑窗不落盘之谜"吃掉了整晚实战数据。
这里每个事件独立 open/append/close, 不经过 stdout 重定向, 稳。
文件: %LOCALAPPDATA%\\BannerlordVoice\\logs\\usage.csv (仅本地)。
"""
import csv
import os
import time
from collections import Counter

from paths import log_dir

_FIELDS = ["ts", "lang", "result", "group", "order", "via", "stt_sec", "heard",
           "engine", "target"]


def _path():
    return os.path.join(log_dir(), "usage.csv")


def record(lang, result, group, order, via, stt_sec, heard, engine="",
           target=""):
    """追加一条使用记录。result: ok/miss。绝不抛异常影响主流程。

    engine: 快路/Whisper (混合识别哪条路出的结果)。
    target: 指向性指令的打击目标兵种 ("骑兵进攻弓箭手"→archers)。
    旧行没有这些列, 读方(recent)统一补空兼容。
    """
    try:
        p = _path()
        new = not os.path.exists(p)
        with open(p, "a", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            if new:
                w.writerow(_FIELDS)
            w.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), lang, result,
                        group or "", order or "", via, f"{stt_sec:.2f}",
                        (heard or "")[:80], engine, target or ""])
    except Exception:
        pass


def recent(n=300):
    """最近 n 条记录(新的在前), 复盘目录用。列表元素为 dict(_FIELDS 键)。

    兼容旧文件: 没有 engine 列的行补空串; 读不了返回空列表。
    """
    try:
        with open(_path(), encoding="utf-8-sig") as f:
            rows = list(csv.reader(f))
    except Exception:
        return []
    if not rows:
        return []
    out = []
    for r in rows[1:]:
        if len(r) < 8:
            continue
        d = dict(zip(_FIELDS, r + [""] * (len(_FIELDS) - len(r))))
        out.append(d)
    out.reverse()
    return out[:n]


def top_commands(lang, n=20, min_rows=40):
    """最常用的前 n 个去重指令组合 [( (group|None, order), 次数 )]。

    数据不足 min_rows 条时返回 None (调用方退回默认题库)。
    """
    try:
        with open(_path(), encoding="utf-8-sig") as f:
            rows = [r for r in csv.DictReader(f)
                    if r.get("result") == "ok" and r.get("lang") == lang
                    and r.get("order")]
    except Exception:
        return None
    if len(rows) < min_rows:
        return None
    c = Counter((r["group"] or None, r["order"]) for r in rows)
    return c.most_common(n)
