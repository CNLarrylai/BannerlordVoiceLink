# Nexus Mods 页面文案(英文,按 Nexus 五段模板)

> 口径与 YouTube 一致:语音补键盘、不替代键盘;不用 "voice mod" 连写(会被搜 Voicemod 破解的人命中),统一 voice command。
> 上传的 zip = 工坊里的 `Modules/BannerlordVoiceLink/` 整个文件夹(含语音程序 exe 与内置模型,约 1.1 GB;由 tools/build_nexus_zip.py 生成),解压到游戏 Modules 目录即可。
> Nexus 页面标题建议:`Voice Commander - command your army by voice`。分类 Gameplay;标签 Voice, Commands, Formations, AI, Utilities。

---

## Description

Voice Commander lets you command your Bannerlord army by talking. Say "archers, shield wall" or "cavalry, charge their horse archers" and the formation does it — no key presses, no cloud, no account. Speech recognition runs entirely on your PC and responds in about 0.1–0.3 seconds.

It is not meant to replace your keyboard. The F-keys are still the fastest way to do simple things. Voice is for the orders that take five key presses, and for the orders the keyboard cannot give at all: attacking a specific enemy formation, splitting a formation mid-battle and placing the halves, moving a formation relative to another one, and triggering the game's own AI tactics (hold the high ground, skirmish, flank, cautious advance) that in vanilla only the AI commander gets to use.

A companion module talks to the game's formation API directly — this is not a macro tool pressing keys through Windows speech recognition. Every order gets a receipt: a banner at the top of the screen and a line in the combat log, so you always know what was heard and who is attacking whom.

Demo video: [YOUTUBE LINK]
Also on Steam Workshop: https://steamcommunity.com/sharedfiles/filedetails/?id=3775571491

## Installation instructions

1. Download and extract. You get one folder: `BannerlordVoiceLink`. Put it in your game's Modules folder, e.g. `C:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord\Modules\BannerlordVoiceLink`.
2. Start the Bannerlord launcher, open Mods, tick **Voice Commander** (BannerlordVoiceLink), load order does not matter. Start the game.
3. On first launch you will see two prompts. Both are expected — allow them:
   - an "unverified code" warning from the game (the module opens a local port to talk to the voice app), and
   - a Windows UAC prompt (the voice app presses keys on your behalf).
4. The voice panel opens with the game. Before your first battle, open **Audio & Recognition settings**:
   - **Microphone**: talk, watch which level bar jumps, select that one, save. If nothing happens in game later, this is the reason nine times out of ten.
   - **Model**: NVIDIA card → download the GPU libraries once (about 1.2 GB) and use the accurate model. No GPU → keep the small model, the big ones are too slow on CPU. Restart the voice app after changing.
5. Optional: run the calibration once. You read the commands out loud and it learns your accent. Only needed if some commands keep getting misheard.
6. Press **F12** to pause listening when you are talking to chat or on a call, so it doesn't fire orders. **F11** opens the review window (what was heard, what was triggered).

If you also subscribe to the Workshop version, enable only one of the two in the launcher.

## Main features

- **Every keyboard order, by voice**: charge, advance, fall back, halt, retreat, follow me, move here, shield wall, line, loose, circle, square, wedge, column, scatter, fire at will, hold fire, mount/dismount, delegate to AI, face direction. Casual phrasings work ("go get them", "spread out", "shields up").
- **Targeted attack** (module only): "Cavalry, charge their archers" — your formation locks onto that enemy formation through the game API. "Attack them" focus-fires whatever enemy is closest to you.
- **Split and command the halves** (module only): "Archers, split" → "Archers left, fire at will" / "Group five, follow me". Groups 5–8 are addressable by number.
- **Relative positioning** (module only): "Cavalry, go to the left of the archers", "Infantry, move in front of the horse archers, 30 meters", "Archers, fall back 20 meters".
- **AI tactics** (module only): hold the high ground, skirmish, flank, advance carefully, guard the left/right flank, protect the archers. Your formation stays under your control — any direct order takes it back. Nothing is delegated to the team AI.
- **On-screen receipts**: top banner plus combat-log line for every order.
- **It learns you**: calibration teaches it your accent; the F11 review window lets you correct a mishearing on the spot; the dictionary is a plain text file you can extend.
- **Privacy**: recognition is fully local. No internet connection is used, no audio leaves your machine.
- **Compatibility**: no Harmony patches, no game files modified — only official APIs. Works alongside most mods (localization, visuals, troops, maps, economy). Command mods such as RTS Camera can be installed together, but issue orders from one at a time. Mods that heavily rewrite formation/battle AI may affect the split and flank features.
- Chinese command set is complete; English is newer and improving. If a phrasing you use is missing, say so in the comments — adding one takes a minute.

## Requirements

- Mount & Blade II: Bannerlord **v1.4.6 or newer** (Steam). Depends only on Native, SandBoxCore and Sandbox — no third-party mods.
- Windows 10/11, any microphone.
- No GPU required (CPU mode). An NVIDIA card is recommended: one click in the settings downloads the CUDA libraries (~1.2 GB) for faster, more accurate recognition.
- About 400 MB of disk space for the module and the bundled voice app. The accurate speech model is an extra download (~1.5 GB) from inside the app.
- Some antivirus products flag the voice app (a common false positive for PyInstaller-packaged programs). There is no malicious code; a code-signed build is planned.

## Shout outs

- **Resonant**, whose 2020 video of VoiceAttack controlling Bannerlord planted the idea six years ago. I used VoiceAttack for a while; this mod exists because I wanted the part it couldn't do.
- **TaleWorlds**, for a formation API rich enough that a companion module can do all of this without patching the game.
- The open-source speech stack this runs on: **OpenAI Whisper** via **faster-whisper**, and **sherpa-onnx** (k2-fsa) for the low-latency streaming engine.
- Built with **Claude Code**. I'm a product manager, not a programmer — the whole mod was written in pair with AI.
- Everyone who sent calibration recordings and bug reports during the beta.
