# -*- coding: utf-8 -*-
"""KWS vs Whisper 头对头基准 (中文命令集)。

用同一批 TTS 语料 (tests/audio/cmd_*.wav 正样本, chat_*.wav 负样本):
  - 命中率: 正样本里期望的 兵种+指令 是否都被识别
  - 误触发: 负样本(聊天)是否被当成命令
  - 延迟: 单样本处理耗时
KWS 侧: sherpa-onnx 关键词检测(流式, 不 reset —— 一句里多个关键词都收)。
Whisper 侧: 复用现有 Transcriber + Matcher。
"""
import glob
import os
import sys
import time

import numpy as np
import soundfile as sf
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

M = os.path.join(HERE, "models", "sherpa-onnx-kws-zipformer-zh-en-3M-2025-12-20")
AUDIO = os.path.join(ROOT, "tests", "audio")


# ---------- KWS ----------

def make_kws():
    import sherpa_onnx
    return sherpa_onnx.KeywordSpotter(
        tokens=f"{M}/tokens.txt",
        encoder=f"{M}/encoder-epoch-13-avg-2-chunk-16-left-64.onnx",
        decoder=f"{M}/decoder-epoch-13-avg-2-chunk-16-left-64.onnx",
        joiner=f"{M}/joiner-epoch-13-avg-2-chunk-16-left-64.onnx",
        keywords_file=f"{HERE}/keywords.txt", num_threads=2)


def kws_spot(kws, samples, sr):
    """流式喂音频, 返回检测到的命令 key 集合 (不 reset: 一句多词都收)。"""
    st = kws.create_stream()
    found = []
    ch = int(sr * 0.1)

    def drain():
        while kws.is_ready(st):
            kws.decode_stream(st)
        r = kws.get_result(st)
        if r:
            found.append(r)

    for i in range(0, len(samples), ch):
        st.accept_waveform(sr, samples[i:i + ch])
        drain()
    st.accept_waveform(sr, np.zeros(int(sr * 0.5), dtype="float32"))
    drain()
    drain()
    return {x.split(":", 1)[1] for x in found}  # {command_key}


# ---------- Whisper ----------

def make_whisper():
    import yaml as y
    from stt import Transcriber
    from matcher import Matcher
    import dictionary
    cfg = y.safe_load(open(os.path.join(ROOT, "config", "settings.yaml"),
                           encoding="utf-8"))
    cfg["stt"]["language"] = "zh"
    tr = Transcriber(cfg)
    cmds = dictionary.load_commands()
    m = Matcher.from_config(cmds, cfg["control"], lang="zh")
    return tr, m


def whisper_spot(tr, m, samples, sr):
    from audio import resample_to_target
    text = tr.transcribe(resample_to_target(samples, sr) if sr != 16000 else samples)
    r = m.parse(text)
    keys = set()
    if r:
        if r.get("group"):
            keys.add(r["group"]["name"])
        if r.get("order"):
            keys.add(r["order"]["name"])
    return keys, text


def load(wav):
    s, sr = sf.read(wav, dtype="float32")
    return (s.mean(axis=1) if s.ndim > 1 else s), sr


def main():
    corpus = yaml.safe_load(open(os.path.join(ROOT, "tests", "corpus.yaml"),
                                 encoding="utf-8"))
    cmds = corpus["commands"]
    chats = corpus.get("chat", [])

    print("加载引擎…")
    kws = make_kws()
    tr, m = make_whisper()

    def bench(spot_fn, name):
        hit, lat = 0, []
        for i, item in enumerate(cmds):
            s, sr = load(os.path.join(AUDIO, f"cmd_{i:02d}.wav"))
            t0 = time.perf_counter()
            keys = spot_fn(s, sr)
            lat.append(time.perf_counter() - t0)
            g, o = item.get("group"), item.get("order")
            if (not g or g in keys) and (not o or o in keys):
                hit += 1
        false_trig = 0
        for j in range(len(chats)):
            p = os.path.join(AUDIO, f"chat_{j:02d}.wav")
            if not os.path.exists(p):
                continue
            s, sr = load(p)
            if spot_fn(s, sr):
                false_trig += 1
        lat.sort()
        p50 = lat[len(lat) // 2] * 1000
        print(f"\n== {name} ==")
        print(f"  命中率: {hit}/{len(cmds)} ({hit/len(cmds)*100:.0f}%)")
        print(f"  误触发(聊天): {false_trig}/{len(chats)}")
        print(f"  延迟 p50: {p50:.0f} ms")
        return hit, false_trig, p50

    bench(lambda s, sr: kws_spot(kws, s, sr), "sherpa-onnx KWS")
    bench(lambda s, sr: whisper_spot(tr, m, s, sr)[0], "Whisper + 匹配层")

    # 逐条看 KWS 漏了哪些
    print("\n== KWS 逐条(只列未全中) ==")
    for i, item in enumerate(cmds):
        s, sr = load(os.path.join(AUDIO, f"cmd_{i:02d}.wav"))
        keys = kws_spot(kws, s, sr)
        g, o = item.get("group"), item.get("order")
        if not ((not g or g in keys) and (not o or o in keys)):
            print(f"  ✗ 「{item['text']}」 spot={sorted(keys)} (期望 {g}/{o})")


if __name__ == "__main__":
    main()
