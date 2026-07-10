# -*- coding: utf-8 -*-
"""归一化策略扫描: 流式 ASR 对输入电平敏感, 找最稳的增益策略。"""
import glob
import os
import sys

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, HERE)

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

import yaml  # noqa: E402

import stream_asr  # noqa: E402
from test_cases import load_cases  # noqa: E402


def norm_none(s):
    return s


def peak(t):
    def f(s):
        p = float(np.abs(s).max())
        return s * (t / p) if 1e-4 < p < t else s
    return f


def rmsn(t):
    def f(s):
        r = float(np.sqrt((s ** 2).mean()))
        if r < 1e-5:
            return s
        g = min(t / r, 0.95 / max(1e-6, float(np.abs(s).max())))  # 不削波
        return s * g
    return f


def main():
    import dictionary
    from matcher import Matcher
    cfg = yaml.safe_load(open(os.path.join(ROOT, "config", "settings.yaml"),
                              encoding="utf-8"))
    cmds = dictionary.load_commands()
    m = Matcher.from_config(cmds, cfg["control"], lang="zh")
    hot = stream_asr.build_hotwords(cmds)
    rec = stream_asr.make_stream(hot)
    cases = load_cases()

    def dec(s, sr):
        st = rec.create_stream()
        st.accept_waveform(sr, s)
        st.accept_waveform(sr, np.zeros(int(sr * 0.5), dtype="float32"))
        st.input_finished()
        while rec.is_ready(st):
            rec.decode_stream(st)
        return rec.get_result(st)

    strategies = [("无", norm_none), ("峰值0.9", peak(0.9)), ("峰值0.5", peak(0.5)),
                  ("rms0.05", rmsn(0.05)), ("rms0.08", rmsn(0.08)),
                  ("rms0.12", rmsn(0.12))]
    for label, fn in strategies:
        hit = tot = 0
        miss = []
        for p in sorted(glob.glob(os.path.join(HERE, "results", "recordings",
                                               "*.wav"))):
            idx = int(os.path.basename(p)[:2]) - 1
            if idx >= len(cases):
                continue
            phrase, g, o, cat = cases[idx]
            if not o:
                continue
            tot += 1
            s, sr = sf.read(p, dtype="float32")
            s = s.mean(axis=1) if s.ndim > 1 else s
            text = dec(fn(s), sr)
            r = m.parse(text)
            keys = set()
            if r:
                if r.get("group"):
                    keys.add(r["group"]["name"])
                if r.get("order"):
                    keys.add(r["order"]["name"])
            ok = (not g or g in keys) and (o in keys)
            hit += ok
            if not ok:
                miss.append(f"「{phrase}」→「{text}」")
        print(f"{label}: {hit}/{tot}  漏: {' '.join(miss)}")


if __name__ == "__main__":
    main()
