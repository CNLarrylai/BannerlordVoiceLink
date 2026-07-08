# -*- coding: utf-8 -*-
"""真人实测: KWS vs Whisper 头对头 (提示跟读, 两引擎同跑, 全程记 CSV)。

用法: .venv\\Scripts\\python kws\\live_compare.py
  屏幕出题 -> 你对麦克风念 -> 两个引擎各自识别 -> 屏幕并排显示 + 记 CSV。
  念完出汇总: 各自命中率 / 延迟 / 分歧条目。
CSV: kws/results/live_compare.csv (每条: 期望 / KWS结果+耗时 / Whisper结果+耗时)。
真人数据比 TTS 靠谱得多 —— 拿它定 KWS 到底行不行, 以及校准阈值。
"""
import csv
import os
import sys
import time

import numpy as np

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

import bench_kws as B  # noqa: E402


def build_prompts(commands=None):
    """出题清单: 直接读 tests/voice_test_cases.md (所有引擎共用的标准用例)。"""
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    from test_cases import load_cases
    return [(phrase, g, o) for phrase, g, o, _cat in load_cases()]


def main():
    import dictionary
    from audio import ContinuousListener
    from stt import Transcriber
    from matcher import Matcher

    commands = dictionary.load_commands()
    prompts = build_prompts(commands)

    print("加载引擎 (KWS + Whisper)…")
    kws = B.make_kws()
    cfg = yaml.safe_load(open(os.path.join(ROOT, "config", "settings.yaml"),
                              encoding="utf-8"))
    cfg["stt"]["language"] = "zh"
    tr = Transcriber(cfg)
    m = Matcher.from_config(commands, cfg["control"], lang="zh")

    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    # 保存每条真人录音, 方便事后离线调 KWS 阈值(用真音频, 不靠 TTS 盲调)
    rec_dir = os.path.join(HERE, "results", "recordings")
    os.makedirs(rec_dir, exist_ok=True)
    import soundfile as sf
    csv_path = os.path.join(HERE, "results", "live_compare.csv")
    new = not os.path.exists(csv_path)
    cf = open(csv_path, "a", newline="", encoding="utf-8-sig")
    w = csv.writer(cf)
    if new:
        w.writerow(["ts", "prompt", "want_group", "want_order",
                    "kws_keys", "kws_ok", "kws_ms",
                    "whisper_text", "whisper_keys", "whisper_ok", "whisper_ms",
                    "hybrid_keys", "hybrid_ok", "hybrid_engine", "hybrid_ms"])

    from hybrid import HybridRecognizer
    hy = HybridRecognizer(kws, B.kws_spot, tr, m, commands)

    listener = ContinuousListener(cfg)
    seg = listener.segments()
    kws_hit = whisper_hit = hybrid_hit = n = 0
    hy_fast = 0

    print(f"\n共 {len(prompts)} 条。看到题目就念, 念完自动进下一条。Ctrl+C 结束。\n")
    try:
        for i, (text, wg, wo) in enumerate(prompts, 1):
            print(f"[{i}/{len(prompts)}] 请念: 「{text}」  ...", end="", flush=True)
            audio = next(seg)
            sr = cfg["audio"]["samplerate"]
            try:  # 录音按序号存(题目顺序由 MD 固定, 序号可反查期望;
                  # 命令 key 含下划线, 别塞进文件名解析)
                sf.write(os.path.join(rec_dir, f"{i:02d}.wav"), audio, sr)
            except Exception:
                pass

            t0 = time.perf_counter()
            kkeys = B.kws_spot(kws, audio, sr)
            kms = (time.perf_counter() - t0) * 1000
            t0 = time.perf_counter()
            wtext = tr.transcribe(audio)
            wr = m.parse(wtext)
            wkeys = set()
            if wr:
                if wr.get("group"):
                    wkeys.add(wr["group"]["name"])
                if wr.get("order"):
                    wkeys.add(wr["order"]["name"])
            wms = (time.perf_counter() - t0) * 1000

            # 混合: 快路=复用已算好的 kkeys; 慢路=复用 wkeys (同一段音频,
            # 不重复计算 —— 延迟按"实际会发生的路径"折算)
            if kkeys & hy.orders:
                hkeys, heng, hms = kkeys, "kws", kms
                hy_fast += 1
            else:
                hkeys, heng, hms = wkeys, "whisper", kms + wms
            hok = (not wg or wg in hkeys) and (not wo or wo in hkeys)

            kok = (not wg or wg in kkeys) and (not wo or wo in kkeys)
            wok = (not wg or wg in wkeys) and (not wo or wo in wkeys)
            n += 1
            kws_hit += kok
            whisper_hit += wok
            hybrid_hit += hok
            print(f"\r[{i}/{len(prompts)}] 「{text}」  "
                  f"KWS {'✓' if kok else '✗'}{sorted(kkeys)} {kms:.0f}ms  |  "
                  f"Whisper {'✓' if wok else '✗'}「{wtext}」{sorted(wkeys)} {wms:.0f}ms"
                  f"  |  混合 {'✓' if hok else '✗'}[{heng}] {hms:.0f}ms")
            w.writerow([time.strftime("%H:%M:%S"), text, wg or "", wo or "",
                        "|".join(sorted(kkeys)), int(kok), f"{kms:.0f}",
                        wtext, "|".join(sorted(wkeys)), int(wok), f"{wms:.0f}",
                        "|".join(sorted(hkeys)), int(hok), heng, f"{hms:.0f}"])
            cf.flush()
    except (KeyboardInterrupt, StopIteration):
        print("\n(结束)")
    finally:
        listener.stop()
        cf.close()

    if n:
        print(f"\n===== 汇总 ({n} 条) =====")
        print(f"  KWS 命中     {kws_hit}/{n} ({kws_hit/n*100:.0f}%)")
        print(f"  Whisper 命中 {whisper_hit}/{n} ({whisper_hit/n*100:.0f}%)")
        print(f"  混合 命中    {hybrid_hit}/{n} ({hybrid_hit/n*100:.0f}%)"
              f"  (快路 {hy_fast}/{n})")
        print(f"  CSV: {csv_path}")


if __name__ == "__main__":
    main()
