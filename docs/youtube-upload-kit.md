# YouTube 上传包(第一期英文演示)

> 封面文件(同目录 `H:\2025录制\粗剪_语音指挥\剪映初稿\`):`封面F_i_talk_to_my_army.jpg` / `封面G_free_voice_mod.jpg` / `封面E_voice_commands.jpg`(1280×720,示意图底)。
> 口径:**语音和键鼠相辅相成** —— 简单动作键鼠更快,复杂指令(定向攻击/分队/相对站位/AI 战术)一句话说完。不用 "no keyboard" 这种替代式说法。
> A/B 测试:YouTube Studio → 视频 → 缩略图"测试与比较",两张都传,跑到有结论为止(通常几天,看播放量)。
> 标题测试是另一个入口(部分账号已开放),没有的话先用标题 A。

## 标题(两组,对应两张封面)

- **配 F(i talk to my army)**:`Free Bannerlord mod: command your army by voice`
- **配 G(FREE voice mod)**:`I talk to my Bannerlord army and it actually listens`
- **配 E(voice commands)**:`Bannerlord won't let you use half its tactics. So I talk to it.`

标题和封面互补不重复:封面有 FREE 的,标题就不放 FREE。

## 标题("I built" 组,2026-09-16 定的主打方向)

主张从"能语音指挥"换成**"这东西是我做的"** —— 个人作者 + 自制工具比单纯功能演示更抓人,
也接得上描述里那段 VoiceAttack 的由来。配套新封面(`C:\Users\Victoria\Videos\骑砍 语音指挥模组 英文 剪映终稿\`,
自拍抠图镜像+声浪,见 `tools/make_thumb_shout.py`):

| # | 标题 | 建议配封面 |
|---|---|---|
| A | `I built a voice commander for Bannerlord — say it, and the army does it` | 封面W(I BUILT THIS / MY ARMY OBEYS) |
| B | `VoiceAttack wasn't enough, so I built my own Bannerlord voice commander` | 封面X(I BUILT IT / AND IT LISTENS) |
| C | `I built voice orders into Bannerlord: targeting, splits, and AI tactics` | 封面V(I BUILT A / VOICE COMMANDER) |
| D | `I built a Bannerlord mod that takes spoken orders (free on the Workshop)` | 封面W / 封面X |
| E | `I made Bannerlord listen to me — here's the mod I built for it` | 封面V / 封面Y |

- A 最稳:前 5 个词就说清"我造的 + 是什么",后半句给结果。
- B 带由来,对老玩家(知道 VoiceAttack)杀伤力最大,但标题里出现别家产品名,曝光初期会被推给 VoiceAttack 的受众 —— 这是好事也是限制。
- C 功能向,配"I BUILT A / VOICE COMMANDER"封面时和封面词重,优先配别的封面或改配 T。
- D 唯一带 free 的,封面就别再放 FREE。
- 都别写 "voice mod" 连写(会命中 Voicemod 破解搜索),也别写 "no keyboard"(违背相辅相成口径 —— 封面U 因此弃用)。

## 描述(直接粘贴)

```
Free voice command mod for Mount & Blade II: Bannerlord — Steam Workshop:
https://steamcommunity.com/sharedfiles/filedetails/?id=3775571491
(It's unlisted for now. I want feedback before going public — the link works, it just doesn't show up in search.)

Say "Archers, shield wall" and they do it. Runs offline on your PC, nothing goes to the cloud.
It's not there to replace your keyboard — the F-keys are still the fastest way to do the simple stuff. It's for the orders that take five key presses, or that the keyboard can't give at all:
• "Cavalry, charge their horse archers" — attack a specific enemy formation
• "Archers, split" → "Group five, go to the right of the infantry" — split a formation mid-battle and place the halves
• "Archers, hold the high ground" / "Horse archers, skirmish" — the game's own AI tactics, normally only the enemy general gets to use them

Chapters
0:00 Intro
0:32 Archers in front, split
0:54 Hold the high ground (AI tactic)
1:41 "Attack them" (targeted attack)
2:38 Shield wall, follow me, skirmish
3:23 Charge
4:12 Horse archers attack their infantry
5:00 Wrap-up

Where this came from
About six years ago I saw Resonant's video of VoiceAttack controlling Bannerlord, and I used it for a while. Even the paid version had trouble with what I actually wanted: adding my own phrasings was clunky, and every command was just a key press — it could never do anything the keyboard couldn't. That's where the idea to build something better came from. With AI coding tools being what they are now, I finally had the time to try. This is that attempt: a companion mod that talks to the game's own formation API instead of pressing keys for you.

Setup
1. Subscribe on the Workshop, enable the mod in the launcher, start the game.
2. First launch shows two popups: an "unverified code" warning (the mod opens a local port) and a UAC prompt (it presses keys for you). Both are expected.
3. Pick the right microphone. In the Audio & Recognition settings window, talk and watch which level bar jumps — select that one and save. If nothing happens in game, this is the reason 9 times out of 10.
4. Pick the right model. NVIDIA card: download the GPU libraries once (about 1.2 GB) and use the accurate model. No GPU: stay on the small model, the big ones are too slow on CPU. Restart the voice app after changing.
5. Calibration is optional. If some commands keep getting misheard, run it once — you read the commands out loud and it learns your accent. English support is new; I'm a Chinese streamer, so it started as a Chinese mod. It learned my accent, it should learn yours.

Still in beta. If a command you want isn't in there, tell me in the comments — the dictionary is a text file, adding one takes a minute.

Not a VoiceAttack profile. A companion mod that talks to the game's own formation API — targeting, splitting, relative positioning, and AI tactics that F-keys can't reach. Keep your keyboard for the rest.

#Bannerlord #MountAndBlade #VoiceCommand #Mod
```

工坊链接已填(ItemID 3775571491)。YouTube 描述里不能出现尖括号,占位符一律用方括号或直接填真值。章节时间戳按 60fps 成片的时间表,如果你后面又改了剪辑要顺一遍。

## 上传设置速查

- 语言 English;字幕上传 `骑砍语音指挥模组演示 60fps 初剪版_字幕.srt`
- 类别 Gaming,游戏 `Mount & Blade II: Bannerlord`
- 不面向儿童:否;AI 内容披露:不勾
- 先传不公开,等 2160p60 处理完再公开;发布时间北京时间早 8-9 点
- 结尾画面:订阅按钮 + Workshop 链接卡片
