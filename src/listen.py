"""测试模式 —— 持续监听, 打印识别+匹配结果, 不发任何按键 (安全调试)。

单独跑: python src/listen.py   或   python src/app.py --mode listen
"""
import os
import sys
import time

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yaml  # noqa: E402

from audio import ContinuousListener  # noqa: E402
from matcher import Matcher  # noqa: E402
from stt import Transcriber  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    with open(os.path.join(ROOT, "config", "settings.yaml"), encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    with open(os.path.join(ROOT, "config", "commands.yaml"), encoding="utf-8") as f:
        commands = yaml.safe_load(f)

    tr = Transcriber(cfg)
    m = Matcher(commands, cfg["control"]["match_threshold"],
                cfg["control"].get("chat_filter", True))
    prefixes = cfg["control"].get("command_prefix") or []
    sr = cfg["audio"]["samplerate"]

    print("\n=== 持续监听中 (不发按键, 仅打印) === Ctrl+C 退出\n")
    if prefixes:
        print(f"已开口令前缀: {prefixes}  (要先说前缀才算指令)\n")

    listener = ContinuousListener(cfg)
    try:
        for audio in listener.segments():
            print(f"[{time.strftime('%H:%M:%S')}] 🎧 捕到语音 {audio.shape[0] / sr:.1f}s")
            t0 = time.perf_counter()
            text = tr.transcribe(audio)
            print(f"    [耗时] 识别 {time.perf_counter() - t0:.2f}s")
            if not text:
                continue
            cleaned = text
            if prefixes:
                hit = next((p for p in prefixes if p in text), None)
                if not hit:
                    print(f"  (忽略, 无口令前缀) 听到: {text}")
                    continue
                cleaned = text.replace(hit, "", 1).strip()
            parsed = m.parse(cleaned)
            if not parsed:
                print(f"  ✗ 未匹配   听到: {text}")
                continue
            g, o = parsed.get("group"), parsed.get("order")
            gs = f"{g['name']}->{g['select']}" if g else "—"
            os_ = f"{o['name']}->{'+'.join(o['keys'])}" if o else "—"
            print(f"  ✓ 兵种:{gs}  指令:{os_}   听到: {text}")
    except KeyboardInterrupt:
        listener.stop()
        print("\n再见。")


if __name__ == "__main__":
    main()
