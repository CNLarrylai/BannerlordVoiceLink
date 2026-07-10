# -*- coding: utf-8 -*-
"""流式 zipformer ASR 作快路候选的离线评测 (用 live_compare 存的真人录音)。

对比三条快路方案在同一批录音上的表现:
  A. KWS 3M (关键词直出)
  B. 流式 zipformer 70M + 现有 matcher (文字→模糊匹配, 支持热词偏置)
  C. Whisper turbo + matcher (基线, 慢)
用法: .venv\\Scripts\\python kws\\bench_stream.py
"""
import glob
import os
import sys
import time

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

import bench_kws as B  # noqa: E402
import stream_asr  # noqa: E402
from test_cases import load_cases  # noqa: E402


def keys_of(m, text):
    """评分用: 取"过了阈值"的兵种/指令, 不要求可执行。

    与执行判定(parse)的差别: 纯兵种句 parse 按设计返回 None(只有兵种
    不执行, 防乱切编队), 但评测里兵种题考察的是"词认没认出来" ——
    用 explain 的 trace 拿 pass 的兵种, 不受执行门槛影响。
    """
    tr = m.explain(text)
    out = set()
    for part in ("group", "order"):
        d = tr.get(part)
        if d and d.get("pass"):
            out.add(d["name"])
    return out


def main():
    import dictionary
    from matcher import Matcher
    from stt import Transcriber

    cases = load_cases()
    recs = sorted(glob.glob(os.path.join(HERE, "results", "recordings", "*.wav")))
    if not recs:
        print("没有录音, 先跑 live_compare。")
        return

    cfg = yaml.safe_load(open(os.path.join(ROOT, "config", "settings.yaml"),
                              encoding="utf-8"))
    cfg["stt"]["language"] = "zh"
    cmds = dictionary.load_commands()
    m = Matcher.from_config(cmds, cfg["control"], lang="zh")

    hot = stream_asr.build_hotwords(cmds)

    print("加载引擎…")
    kws = B.make_kws()
    stream0 = stream_asr.make_stream()      # 裸流式
    stream_h = stream_asr.make_stream(hot)  # 流式+热词
    tr = Transcriber(cfg)

    stats = {k: {"hit": 0, "ms": []}
             for k in ("kws", "stream", "stream_hot", "whisper")}
    tot = 0
    detail = []
    for p in recs:
        idx = int(os.path.basename(p)[:2]) - 1
        if idx >= len(cases):
            continue
        phrase, g, o, cat = cases[idx]
        tot += 1
        s, sr = sf.read(p, dtype="float32")
        s = s.mean(axis=1) if s.ndim > 1 else s

        t0 = time.perf_counter()
        kk = B.kws_spot(kws, s, sr)
        stats["kws"]["ms"].append((time.perf_counter() - t0) * 1000)
        kok = (not g or g in kk) and (not o or o in kk)
        stats["kws"]["hit"] += kok

        t0 = time.perf_counter()
        stext = stream_asr.transcribe(stream0, s, sr)
        sk = keys_of(m, stext)
        stats["stream"]["ms"].append((time.perf_counter() - t0) * 1000)
        sok = (not g or g in sk) and (not o or o in sk)
        stats["stream"]["hit"] += sok

        t0 = time.perf_counter()
        htext = stream_asr.transcribe(stream_h, s, sr)
        hk = keys_of(m, htext)
        stats["stream_hot"]["ms"].append((time.perf_counter() - t0) * 1000)
        hok = (not g or g in hk) and (not o or o in hk)
        stats["stream_hot"]["hit"] += hok

        t0 = time.perf_counter()
        wtext = tr.transcribe(s)
        wk = keys_of(m, wtext)
        stats["whisper"]["ms"].append((time.perf_counter() - t0) * 1000)
        wok = (not g or g in wk) and (not o or o in wk)
        stats["whisper"]["hit"] += wok

        detail.append((phrase, kok, sok, stext, hok, htext, wok, wtext))

    import statistics as st
    print(f"\n===== 同一批真人录音 {tot} 条 (含纯兵种题) =====")
    names = {"kws": "KWS 3M        ", "stream": "流式ASR 裸    ",
             "stream_hot": "流式ASR+热词  ", "whisper": "Whisper turbo "}
    for k, v in stats.items():
        print(f"  {names[k]} 命中 {v['hit']}/{tot} ({v['hit']/tot*100:.0f}%)  "
              f"延迟中位 {st.median(v['ms']):.0f}ms")
    print("\n===== 逐条 (✗的引擎标出) =====")
    for phrase, kok, sok, stext, hok, htext, wok, wtext in detail:
        if kok and sok and hok and wok:
            continue
        marks = []
        if not kok:
            marks.append("KWS✗")
        if not sok:
            marks.append(f"流裸✗「{stext}」")
        if not hok:
            marks.append(f"流热✗「{htext}」")
        if not wok:
            marks.append(f"W✗「{wtext}」")
        print(f"  「{phrase}」 {' | '.join(marks)}")


if __name__ == "__main__":
    main()
