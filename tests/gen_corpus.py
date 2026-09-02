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


# 英文用两个母语声音各合成一份 (文件名带声音标签), 语料白拿翻倍
EN_VOICES = ("Zira", "David")


def make_voice(want=("Huihui", "Chinese")):
    v = comtypes.client.CreateObject("SAPI.SpVoice")
    for voice in v.GetVoices():
        d = voice.GetDescription()
        if any(w in d for w in want):
            v.Voice = voice
            print(f"[TTS] 声音: {d}")
            return v
    print(f"[TTS] ⚠ 没找到声音 {want}, 结果可能不准")
    return v


def speak_to_wav(voice, text, path):
    stream = comtypes.client.CreateObject("SAPI.SpFileStream")
    stream.Open(path, SSFM_CREATE_FOR_WRITE)
    voice.AudioOutputStream = stream
    voice.Speak(text)
    stream.Close()


def main():
    lang = "en" if "--lang" in sys.argv and sys.argv[sys.argv.index("--lang") + 1] == "en" else "zh"
    corpus_file = "corpus_en.yaml" if lang == "en" else "corpus.yaml"
    with open(os.path.join(HERE, corpus_file), encoding="utf-8") as f:
        corpus = yaml.safe_load(f)
    # (文件名标签, 声音) 列表: 中文一份, 英文每个声音一份
    voices = ([(f"en_{v.lower()}", make_voice((v,))) for v in EN_VOICES]
              if lang == "en" else [("", make_voice())])
    n = 0
    for tag, voice in voices:
        for kind, key in (("cmd", "commands"), ("chat", "chat")):
            for i, item in enumerate(corpus.get(key, [])):
                name = f"{tag}_{kind}_{i:02d}.wav" if tag else f"{kind}_{i:02d}.wav"
                path = os.path.join(AUDIO, name)
                speak_to_wav(voice, item["text"], path)
                ok = os.path.exists(path) and os.path.getsize(path) > 1000
                print(f"  {'✓' if ok else '✗'} {name}  「{item['text']}」")
                n += ok
    print(f"\n生成完成: {n} 个语音 -> {AUDIO}")


if __name__ == "__main__":
    main()
