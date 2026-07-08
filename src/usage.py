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

_FIELDS = ["ts", "lang", "result", "group", "order", "via", "stt_sec", "heard"]


def _path():
    return os.path.join(log_dir(), "usage.csv")


def record(lang, result, group, order, via, stt_sec, heard):
    """追加一条使用记录。result: ok/miss。绝不抛异常影响主流程。"""
    try:
        p = _path()
        new = not os.path.exists(p)
        with open(p, "a", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            if new:
                w.writerow(_FIELDS)
            w.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), lang, result,
                        group or "", order or "", via, f"{stt_sec:.2f}",
                        (heard or "")[:80]])
    except Exception:
        pass


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
