# -*- coding: utf-8 -*-
"""纯CPU下各 Whisper 模型的速度/命中实测 —— 给 auto 分档定依据。

粉丝默认走 CPU(没下 CUDA 库), 所以"默认模型"必须按 CPU 上的真实耗时选。
用真人录音(kws/results/recordings)跑, 不用 TTS。
用法: .venv\\Scripts\\python tests\\bench_cpu_models.py
"""
import glob
import os
import statistics
import sys
import time

import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, HERE)

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

import yaml  # noqa: E402

from test_cases import load_cases  # noqa: E402

MODELS = ["base", "small", "medium", "large-v3-turbo"]


def main():
    import dictionary
    from matcher import Matcher
    from stt import Transcriber

    # 语料优先真人录音; 没有就用 TTS 黄金语料(tests/audio/cmd_*.wav + corpus.yaml)
    cases = load_cases()
    recs = sorted(glob.glob(os.path.join(ROOT, "kws", "results",
                                         "recordings", "*.wav")))
    use_tts = not recs
    if use_tts:
        corpus = yaml.safe_load(open(os.path.join(HERE, "corpus.yaml"),
                                     encoding="utf-8"))
        items = corpus["commands"]
        recs = [os.path.join(HERE, "audio", f"cmd_{i:02d}.wav")
                for i in range(len(items))]
        recs = [p for p in recs if os.path.exists(p)]
        cases = [(items[i].get("text", ""), items[i].get("group"),
                  items[i].get("order"), "") for i in range(len(recs))]
        print("(用 TTS 黄金语料; 真人录音更可信, 有的话优先)")
    if not recs:
        print("没有可用语料")
        return
    cfg0 = yaml.safe_load(open(os.path.join(ROOT, "config", "settings.yaml"),
                               encoding="utf-8"))
    cmds = dictionary.load_commands()
    m = Matcher.from_config(cmds, cfg0["control"], lang="zh")

    print(f"录音 {len(recs)} 条, 强制 CPU/int8\n")
    for name in MODELS:
        cfg = yaml.safe_load(open(os.path.join(ROOT, "config", "settings.yaml"),
                                  encoding="utf-8"))
        cfg["stt"].update(language="zh", model=name, device="cpu",
                          compute_type="int8")
        try:
            tr = Transcriber(cfg)
        except Exception as e:
            print(f"{name}: 加载失败 {e}")
            continue
        hit = tot = 0
        lat = []
        for i, p in enumerate(recs):
            idx = i if use_tts else int(os.path.basename(p)[:2]) - 1
            if idx >= len(cases):
                continue
            phrase, g, o, _c = cases[idx]
            s, sr = sf.read(p, dtype="float32")
            s = s.mean(axis=1) if s.ndim > 1 else s
            t0 = time.perf_counter()
            text = tr.transcribe(s)
            lat.append(time.perf_counter() - t0)
            tot += 1
            trace = m.explain(text)
            keys = set()
            for part in ("group", "order"):
                dd = trace.get(part)
                if dd and dd.get("pass"):
                    keys.add(dd["name"])
            if (not g or g in keys) and (not o or o in keys):
                hit += 1
        print(f"{name:16s} 命中 {hit}/{tot} ({hit/max(1,tot)*100:.0f}%)  "
              f"CPU延迟 中位{statistics.median(lat):.2f}s  "
              f"最慢{max(lat):.2f}s")


if __name__ == "__main__":
    main()
