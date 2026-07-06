"""麦克风自测 —— 录一段话, 看识别结果 + 解析出的指令 (不发按键, 不用进游戏)。

用法: run_mic.bat  或  .venv\Scripts\python tools\test_mic.py
"""
import os
import sys
import time

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np  # noqa: E402
import sounddevice as sd  # noqa: E402
import yaml  # noqa: E402

from matcher import Matcher  # noqa: E402
from stt import Transcriber  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(ROOT, "config", "settings.yaml"), encoding="utf-8") as f:
    cfg = yaml.safe_load(f)
with open(os.path.join(ROOT, "config", "commands.yaml"), encoding="utf-8") as f:
    commands = yaml.safe_load(f)

SR = cfg["audio"]["samplerate"]
SECONDS = 4

tr = Transcriber(cfg)
m = Matcher(commands, cfg["control"]["match_threshold"])

print(f"\n准备好后按回车, 会录音 {SECONDS} 秒, 对着麦克风说一条指令 (如: 弓箭手散开)")
while True:
    try:
        input("\n[回车开始录音, Ctrl+C 退出] ")
    except (EOFError, KeyboardInterrupt):
        print("\n再见。")
        break

    print("🎙 录音中…")
    audio = sd.rec(int(SECONDS * SR), samplerate=SR, channels=1,
                   dtype="float32", device=cfg["audio"]["device"])
    sd.wait()
    audio = audio.flatten()

    rms = float(np.sqrt(np.mean(audio ** 2)))
    t0 = time.time()
    text = tr.transcribe(audio)
    dt = time.time() - t0
    print(f"  音量 RMS={rms:.4f}   识别耗时={dt:.2f}s")
    print(f"  听到: 「{text}」")

    parsed = m.parse(text)
    if not parsed:
        print("  解析: ✗ 没匹配到指令")
        continue
    g, o = parsed.get("group"), parsed.get("order")
    if g:
        print(f"  兵种: {g['name']} -> 按 {g['select']} (分 {g['score']})")
    if o:
        print(f"  指令: {o['name']} -> 按 {'+'.join(o['keys'])} (分 {o['score']})")
