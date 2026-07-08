# -*- coding: utf-8 -*-
"""离线调参: 用 live_compare 存下的真人录音(按序号)重跑 KWS, 扫阈值/看漏词。

录音 results/recordings/NN.wav 对应 voice_test_cases.md 第 NN 条(序号即题号,
命令 key 含下划线, 故不塞文件名 —— 反查用 MD 顺序)。
用法: .venv\\Scripts\\python kws\\tune_offline.py
"""
import glob
import os
import sys

import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tests"))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

import bench_kws as B  # noqa: E402
from test_cases import load_cases  # noqa: E402


def main():
    cases = load_cases()   # 顺序与 live_compare 出题一致, 序号→(phrase,g,o)
    recs = sorted(glob.glob(os.path.join(HERE, "results", "recordings", "*.wav")))
    if not recs:
        print("没有录音。先跑一轮 kws/live_compare.py。")
        return
    kws = B.make_kws()
    hit = tot = 0
    miss = []
    for p in recs:
        idx = int(os.path.basename(p)[:2]) - 1     # 01.wav -> 第0条
        if idx < 0 or idx >= len(cases):
            continue
        phrase, g, o, cat = cases[idx]
        if not o:                                  # 只算有指令的现实题
            continue
        tot += 1
        s, sr = sf.read(p, dtype="float32")
        s = s.mean(axis=1) if s.ndim > 1 else s
        keys = B.kws_spot(kws, s, sr)
        ok = (not g or g in keys) and (o in keys)
        hit += ok
        if not ok:
            miss.append((phrase, sorted(keys)))
    print(f"\n录音 {tot} 条现实题, KWS 命中 {hit}/{tot} ({hit/max(1,tot)*100:.0f}%)")
    if miss:
        print("漏的:")
        for phrase, keys in miss:
            print(f"  「{phrase}」 spot={keys}")


if __name__ == "__main__":
    main()
