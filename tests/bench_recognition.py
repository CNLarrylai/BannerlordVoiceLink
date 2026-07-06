"""识别基准 —— 把语音语料跑真实引擎, 量化命中率 + 延迟, 记入历史。

用法:
  python tests/bench_recognition.py                  # 用 settings.yaml 当前配置
  python tests/bench_recognition.py --model small    # 临时换模型对比
  python tests/bench_recognition.py --device cpu --compute int8 --note 无显卡模拟

输出: 命令命中率、聊天误触数、延迟 avg/p50/p95, 并追加一行到
      tests/results/history.csv (方便长期追踪每次改动的影响)。
"""
import argparse
import os
import sys
from datetime import datetime

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

import time

import soundfile as sf
import yaml

from audio import resample_to_target
from matcher import Matcher
from stt import Transcriber


def pct(data, p):
    if not data:
        return 0.0
    s = sorted(data)
    k = (len(s) - 1) * p
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model")
    ap.add_argument("--device")
    ap.add_argument("--compute")
    ap.add_argument("--note", default="")
    args = ap.parse_args()

    with open(os.path.join(ROOT, "config", "settings.yaml"), encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    with open(os.path.join(ROOT, "config", "commands.yaml"), encoding="utf-8") as f:
        commands = yaml.safe_load(f)
    with open(os.path.join(HERE, "corpus.yaml"), encoding="utf-8") as f:
        corpus = yaml.safe_load(f)

    if args.model:
        cfg["stt"]["model"] = args.model
    if args.device:
        cfg["stt"]["device"] = args.device
    if args.compute:
        cfg["stt"]["compute_type"] = args.compute

    tr = Transcriber(cfg)
    m = Matcher(commands, cfg["control"]["match_threshold"],
                cfg["control"].get("chat_filter", True))
    audio_dir = os.path.join(HERE, "audio")

    def load(name):
        a, sr = sf.read(os.path.join(audio_dir, name), dtype="float32")
        if a.ndim > 1:
            a = a.mean(axis=1)
        return resample_to_target(a, sr)

    # ---- 命令 (正样本) ----
    print("\n=== 命令识别 ===")
    lat, hits, cmd_misses = [], 0, []
    cmds = corpus.get("commands", [])
    for i, item in enumerate(cmds):
        wav = f"cmd_{i:02d}.wav"
        if not os.path.exists(os.path.join(audio_dir, wav)):
            print(f"  ⚠ 缺 {wav}, 先跑 gen_corpus.py")
            continue
        t0 = time.perf_counter()
        text = tr.transcribe(load(wav))
        lat.append((time.perf_counter() - t0) * 1000)
        r = m.parse(text)
        g = r["group"]["name"] if r and r["group"] else None
        o = r["order"]["name"] if r and r["order"] else None
        ok = (o == item["order"]) and (g == item["group"])
        hits += ok
        if not ok:
            cmd_misses.append((item["text"], text, f"{g}/{o}",
                               f"{item['group']}/{item['order']}"))
        print(f"  {'✓' if ok else '✗'} 「{item['text']}」 听到「{text}」 -> {g}/{o}")

    # ---- 聊天 (负样本) ----
    print("\n=== 聊天误触 ===")
    false_trig = []
    chats = corpus.get("chat", [])
    for i, item in enumerate(chats):
        wav = f"chat_{i:02d}.wav"
        if not os.path.exists(os.path.join(audio_dir, wav)):
            continue
        text = tr.transcribe(load(wav))
        r = m.parse(text)
        triggered = r is not None
        if triggered:
            false_trig.append((item["text"], text))
        print(f"  {'✗ 误触!' if triggered else '✓ 忽略'} 「{item['text']}」 听到「{text}」")

    # ---- 汇总 ----
    n_cmd = len([1 for i in range(len(cmds))
                 if os.path.exists(os.path.join(audio_dir, f"cmd_{i:02d}.wav"))])
    n_chat = len([1 for i in range(len(chats))
                  if os.path.exists(os.path.join(audio_dir, f"chat_{i:02d}.wav"))])
    acc = hits / n_cmd * 100 if n_cmd else 0
    s = cfg["stt"]
    print("\n" + "=" * 52)
    print(f"模型={s['model']} 设备={s['device']} 量化={s['compute_type']}")
    print(f"命令命中: {hits}/{n_cmd} = {acc:.1f}%   聊天误触: {len(false_trig)}/{n_chat}")
    print(f"延迟(ms): 平均 {sum(lat)/len(lat):.0f} | p50 {pct(lat,0.5):.0f} | "
          f"p95 {pct(lat,0.95):.0f}")
    if cmd_misses:
        print("漏掉的命令:")
        for txt, heard, got, want in cmd_misses:
            print(f"    「{txt}」 听成「{heard}」 得到 {got} (应 {want})")

    # ---- 追加历史 ----
    res_dir = os.path.join(HERE, "results")
    os.makedirs(res_dir, exist_ok=True)
    hist = os.path.join(res_dir, "history.csv")
    new = not os.path.exists(hist)
    # 新建时用 utf-8-sig(带 BOM), 让 Excel 在中文 Windows 下不乱码; 追加用 utf-8
    with open(hist, "a", encoding="utf-8-sig" if new else "utf-8") as f:
        if new:
            f.write("时间,模型,设备,量化,命令数,命中,命中率%,聊天数,误触,"
                    "延迟avg_ms,延迟p50_ms,延迟p95_ms,备注\n")
        f.write(f"{datetime.now():%Y-%m-%d %H:%M},{s['model']},{s['device']},"
                f"{s['compute_type']},{n_cmd},{hits},{acc:.1f},{n_chat},"
                f"{len(false_trig)},{sum(lat)/len(lat):.0f},{pct(lat,0.5):.0f},"
                f"{pct(lat,0.95):.0f},{args.note}\n")
    print(f"\n已记入历史: {hist}")


if __name__ == "__main__":
    main()
