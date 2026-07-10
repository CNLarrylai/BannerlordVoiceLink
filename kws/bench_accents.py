# -*- coding: utf-8 -*-
"""方言口音基准 —— 用微软 Edge TTS 的地方口音声线合成指令, 测三引擎鲁棒性。

声线: 标准普通话(男/女) + 东北(辽宁) + 陕西 + 台湾(男/女)。
用例: tests/voice_test_cases.md (统一标准答案)。
合成音频缓存在 kws/audio_accents/<声线>/NN.mp3, 重跑不重新联网合成。

注意: TTS 口音 ≠ 真人口音(合成音更"标准"), 结果只作方向参考 ——
系统性、跨声线的同类失败才值得修; 单声线单条的伪影别追。
用法: .venv\\Scripts\\python kws\\bench_accents.py [--regen]
"""
import asyncio
import os
import sys

import numpy as np

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

VOICES = [
    ("标准女", "zh-CN-XiaoxiaoNeural"),
    ("标准男", "zh-CN-YunjianNeural"),
    ("东北", "zh-CN-liaoning-XiaobeiNeural"),
    ("陕西", "zh-CN-shaanxi-XiaoniNeural"),
    ("台湾女", "zh-TW-HsiaoChenNeural"),
    ("台湾男", "zh-TW-YunJheNeural"),
]
AUD = os.path.join(HERE, "audio_accents")


def load_mp3(path, sr=16000):
    """mp3 -> float32 单声道 16k (av 解码, faster-whisper 的依赖, 无需 ffmpeg)。"""
    import av
    out = []
    with av.open(path) as c:
        rs = av.AudioResampler(format="s16", layout="mono", rate=sr)
        for frame in c.decode(audio=0):
            res = rs.resample(frame)
            frames = res if isinstance(res, list) else [res]
            for f in frames:
                if f is not None:
                    out.append(f.to_ndarray().reshape(-1))
    if not out:
        return np.zeros(sr, dtype="float32")
    return (np.concatenate(out).astype("float32") / 32768.0)


def clip_path(vid, phrase):
    """缓存文件名 = 内容哈希 —— 用例表增删改行都不会错位 (题号会, 已踩过)。"""
    import hashlib
    h = hashlib.md5(phrase.encode("utf-8")).hexdigest()[:10]
    return os.path.join(AUD, vid, f"{h}.mp3")


async def synth_all(cases, regen=False):
    import edge_tts
    for vname, vid in VOICES:
        os.makedirs(os.path.join(AUD, vid), exist_ok=True)
        todo = []
        for phrase, _g, _o, _c in cases:
            p = clip_path(vid, phrase)
            if regen or not os.path.exists(p) or os.path.getsize(p) < 500:
                todo.append((phrase, p))
        if todo:
            print(f"[合成] {vname}: {len(todo)} 条…")
        for phrase, p in todo:
            await edge_tts.Communicate(phrase, vid).save(p)


def keys_of(m, text):
    tr = m.explain(text)
    out = set()
    for part in ("group", "order"):
        d = tr.get(part)
        if d and d.get("pass"):
            out.add(d["name"])
    return out


def main():
    regen = "--regen" in sys.argv
    cases = load_cases()
    print(f"用例 {len(cases)} 条 × 声线 {len(VOICES)} 个")
    asyncio.run(synth_all(cases, regen))

    import dictionary
    from matcher import Matcher
    from stt import Transcriber
    cfg = yaml.safe_load(open(os.path.join(ROOT, "config", "settings.yaml"),
                              encoding="utf-8"))
    cfg["stt"]["language"] = "zh"
    cmds = dictionary.load_commands()
    m = Matcher.from_config(cmds, cfg["control"], lang="zh")
    print("加载引擎…")
    stream = stream_asr.make_stream(stream_asr.build_hotwords(cmds))
    tr = Transcriber(cfg)

    grand = {}
    fail_by_case = {}
    for vname, vid in VOICES:
        st = {"stream": 0, "whisper": 0, "hybrid": 0}
        fails = []
        for phrase, g, o, _c in cases:
            p = clip_path(vid, phrase)
            if not os.path.exists(p):
                continue
            s = load_mp3(p)
            stext = stream_asr.transcribe(stream, s, 16000)
            sk = keys_of(m, stext)
            wtext = tr.transcribe(s)
            wk = keys_of(m, wtext)
            want = ((not g or g in sk) and (not o or o in sk),
                    (not g or g in wk) and (not o or o in wk))
            sok, wok = want
            # 混合: 快路解出指令(order)则直出, 否则 whisper 兜底
            hok = sok if (sk & set(cmds["orders"])) else wok
            st["stream"] += sok
            st["whisper"] += wok
            st["hybrid"] += hok
            if not hok:
                fails.append((phrase, stext, wtext))
                fail_by_case.setdefault(phrase, []).append(vname)
        n = len(cases)
        grand[vname] = st
        print(f"\n== {vname} ({vid}) ==")
        print(f"  流式+热词 {st['stream']}/{n}  Whisper {st['whisper']}/{n}  "
              f"混合 {st['hybrid']}/{n}")
        for phrase, stext, wtext in fails:
            print(f"  ✗ 「{phrase}」 流式听「{stext}」 W听「{wtext}」")

    print("\n===== 跨声线汇总 (混合引擎) =====")
    n = len(cases)
    for vname, st in grand.items():
        print(f"  {vname:6s} {st['hybrid']}/{n} ({st['hybrid']/n*100:.0f}%)")
    print("\n===== 系统性失败 (≥2 个声线都倒的用例) =====")
    sys_fail = {k: v for k, v in fail_by_case.items() if len(v) >= 2}
    if not sys_fail:
        print("  (无 —— 失败都是孤立伪影)")
    for phrase, voices in sorted(sys_fail.items(), key=lambda x: -len(x[1])):
        print(f"  「{phrase}」 倒于: {', '.join(voices)}")


if __name__ == "__main__":
    main()
