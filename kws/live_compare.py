# -*- coding: utf-8 -*-
"""真人实测: 流式ASR vs Whisper vs 混合 三方头对头 (提示跟读, 全程记 CSV)。

用法: .venv\\Scripts\\python kws\\live_compare.py
  屏幕出题 -> 你对麦克风念 -> 三个引擎各自识别 -> 屏幕并排显示 + 记 CSV。
  念完出汇总: 各自命中率 / 延迟 / 分歧条目。
CSV: kws/results/live_compare.csv
  (历史轮转: v1_no_hybrid=KWS/Whisper 两方, v2_kws_hybrid=KWS快路混合)
真人数据比 TTS 靠谱得多 —— 换说话人(如让家人念)是快路引擎的照妖镜。
"""
import csv
import os
import sys
import time

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

import stream_asr  # noqa: E402


def build_prompts():
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
    prompts = build_prompts()

    print("加载引擎 (流式ASR + Whisper)…")
    cfg = yaml.safe_load(open(os.path.join(ROOT, "config", "settings.yaml"),
                              encoding="utf-8"))
    cfg["stt"]["language"] = "zh"
    hot = stream_asr.build_hotwords(commands)
    stream = stream_asr.make_stream(hot)
    tr = Transcriber(cfg)
    m = Matcher.from_config(commands, cfg["control"], lang="zh")

    def keys_of(text):
        """评分口径: 取"过了阈值"的兵种/指令, 不要求可执行 —— 纯兵种题
        parse 按设计返回 None(只有兵种不执行), 但题目考察的是词认没认出。"""
        tr_ = m.explain(text)
        keys = set()
        for part in ("group", "order"):
            d = tr_.get(part)
            if d and d.get("pass"):
                keys.add(d["name"])
        return keys

    orders = set(commands.get("orders", {}))

    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    # 保存每条真人录音, 方便事后离线重跑 (kws/bench_stream.py 用真音频调参)
    rec_dir = os.path.join(HERE, "results", "recordings")
    os.makedirs(rec_dir, exist_ok=True)
    import soundfile as sf
    csv_path = os.path.join(HERE, "results", "live_compare.csv")
    old = os.path.join(HERE, "results", "live_compare_v2_kws_hybrid.csv")
    if os.path.exists(csv_path) and not os.path.exists(old):
        os.rename(csv_path, old)   # 旧轮(KWS快路)存档, 新轮从头记
    new = not os.path.exists(csv_path)
    cf = open(csv_path, "a", newline="", encoding="utf-8-sig")
    w = csv.writer(cf)
    if new:
        w.writerow(["ts", "prompt", "want_group", "want_order",
                    "stream_text", "stream_keys", "stream_ok", "stream_ms",
                    "whisper_text", "whisper_keys", "whisper_ok", "whisper_ms",
                    "hybrid_keys", "hybrid_ok", "hybrid_engine", "hybrid_ms"])

    listener = ContinuousListener(cfg)
    seg = listener.segments()
    s_hit = w_hit = h_hit = n = 0
    hy_fast = 0

    print(f"\n共 {len(prompts)} 条。看到题目就念, 念完自动进下一条。Ctrl+C 结束。\n")
    try:
        for i, (text, wg, wo) in enumerate(prompts, 1):
            print(f"[{i}/{len(prompts)}] 请念: 「{text}」  ...", end="", flush=True)
            audio = next(seg)
            sr = cfg["audio"]["samplerate"]
            try:  # 录音按序号存(题目顺序由 MD 固定, 序号可反查期望)
                sf.write(os.path.join(rec_dir, f"{i:02d}.wav"), audio, sr)
            except Exception:
                pass

            t0 = time.perf_counter()
            stext = stream_asr.transcribe(stream, audio, sr)
            skeys = keys_of(stext)
            sms = (time.perf_counter() - t0) * 1000
            t0 = time.perf_counter()
            wtext = tr.transcribe(audio)
            wkeys = keys_of(wtext)
            wms = (time.perf_counter() - t0) * 1000

            # 混合: 快路=复用流式结果; 慢路=复用 Whisper (同一段音频不重复算,
            # 延迟按"实际会发生的路径"折算)
            if skeys & orders:
                hkeys, heng, hms = skeys, "stream", sms
                hy_fast += 1
            else:
                hkeys, heng, hms = wkeys, "whisper", sms + wms
            hok = (not wg or wg in hkeys) and (not wo or wo in hkeys)

            sok = (not wg or wg in skeys) and (not wo or wo in skeys)
            wok = (not wg or wg in wkeys) and (not wo or wo in wkeys)
            n += 1
            s_hit += sok
            w_hit += wok
            h_hit += hok
            print(f"\r[{i}/{len(prompts)}] 「{text}」  "
                  f"流式 {'✓' if sok else '✗'}「{stext}」{sorted(skeys)} {sms:.0f}ms | "
                  f"Whisper {'✓' if wok else '✗'}「{wtext}」{sorted(wkeys)} {wms:.0f}ms"
                  f" | 混合 {'✓' if hok else '✗'}[{heng}] {hms:.0f}ms")
            w.writerow([time.strftime("%H:%M:%S"), text, wg or "", wo or "",
                        stext, "|".join(sorted(skeys)), int(sok), f"{sms:.0f}",
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
        print(f"  流式ASR+热词 命中 {s_hit}/{n} ({s_hit/n*100:.0f}%)")
        print(f"  Whisper 命中     {w_hit}/{n} ({w_hit/n*100:.0f}%)")
        print(f"  混合 命中        {h_hit}/{n} ({h_hit/n*100:.0f}%)"
              f"  (快路直出 {hy_fast}/{n})")
        print(f"  CSV: {csv_path}")


if __name__ == "__main__":
    main()
