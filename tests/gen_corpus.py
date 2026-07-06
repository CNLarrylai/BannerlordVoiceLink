"""从 corpus.yaml 合成测试语音 (Windows SAPI 中文 TTS) 到 tests/audio/。

改动/新增语料后跑一次: python tests/gen_corpus.py
生成 tests/audio/cmd_00.wav / chat_00.wav ... 与 corpus 顺序对应。

用 comtypes 直连 SAPI (同步、可靠); pyttsx3 的 runAndWait 循环会卡死, 已弃用。
"""
import os
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

import comtypes.client
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
AUDIO = os.path.join(HERE, "audio")
os.makedirs(AUDIO, exist_ok=True)

SSFM_CREATE_FOR_WRITE = 3


def make_voice():
    v = comtypes.client.CreateObject("SAPI.SpVoice")
    for voice in v.GetVoices():
        d = voice.GetDescription()
        if "Huihui" in d or "Chinese" in d:
            v.Voice = voice
            print(f"[TTS] 中文声音: {d}")
            return v
    print("[TTS] ⚠ 没找到中文声音, 结果可能不准")
    return v


def speak_to_wav(voice, text, path):
    stream = comtypes.client.CreateObject("SAPI.SpFileStream")
    stream.Open(path, SSFM_CREATE_FOR_WRITE)
    voice.AudioOutputStream = stream
    voice.Speak(text)
    stream.Close()


def main():
    with open(os.path.join(HERE, "corpus.yaml"), encoding="utf-8") as f:
        corpus = yaml.safe_load(f)
    voice = make_voice()
    n = 0
    for kind, key in (("cmd", "commands"), ("chat", "chat")):
        for i, item in enumerate(corpus.get(key, [])):
            path = os.path.join(AUDIO, f"{kind}_{i:02d}.wav")
            speak_to_wav(voice, item["text"], path)
            ok = os.path.exists(path) and os.path.getsize(path) > 1000
            print(f"  {'✓' if ok else '✗'} {kind}_{i:02d}  「{item['text']}」")
            n += ok
    print(f"\n生成完成: {n} 个语音 -> {AUDIO}")


if __name__ == "__main__":
    main()
