# English Intro Video Script — "Bannerlord won't let you use half its tactics. So I talk to it."

> 用法:**实况只喊加粗的指令,不说话;旁白(VO)后期对着画面配。**
> 2026-09-07 第一次即兴试录的复盘已并入本稿:旁白被当指令执行了两次("The first one" → 跟随我,
> "Right." → 圆阵),所以旁白必须后配;指令识别本身 0.2~0.3 秒满分,没问题。
> 口播全部短句、主动语态,句首不要 So / like / basically / usually。
> 所有加粗指令已过英文 matcher 路由验证(每条满分),**别临场改词**。
> 括号里是中文镜头/操作提示。

## Pre-script planning

- **Target audience**: Bannerlord players who already command formations and hate juggling F-keys mid-fight. They know what a shield wall is. They don't know the game has an AI layer.
- **Desired emotion**: surprise → "wait, it can do *that*?"
- **Core promise**: In five minutes you'll see an army obey your voice, do things the keyboard physically can't, and learn it's free.
- **Title keyword**: Bannerlord voice command

**High-shock facts (惊讶分)**
1. (90) Every formation has an AI brain with tactics — hold high ground, skirmish, cautious advance — and the player is never allowed to trigger them. Only the enemy general gets to use them.
2. (85) You can't split a formation mid-battle from the keyboard. The game has 8 slots; you just can't reach them.
3. (85) "Cavalry, go to the left of the archers." Vanilla has no order for "next to another formation". It's a sentence here.
4. (80) If you delegate a formation to the AI (F6), the *team* AI can quietly merge your infantry and archers into one blob. This mod runs tactics without delegating.
5. (75) The whole thing runs offline on your PC, and answers in about 0.2 seconds.
6. (70) "Cavalry, charge their horse archers" is a real API lock-on. In vanilla you have to hover the cursor on their icon first.
7. (60) It learned a Chinese accent. "All units" heard as "Or unit" still charges.
8. (85) Voice control in Bannerlord is not new: Resonant showed VoiceAttack doing it in April 2020 (26k views). That was a macro tool — your voice pressed F-keys through Windows speech recognition. Top comments: "train Windows speech recognition more than once", "my accent is too Glaswegian for this". Every one of those is a thing this mod fixes.

---

## HOOK (0:00–0:20)

(画面 0 秒:骑马砍人中,直接喊。别用 "All right" 起手,会解析成右队)

> **"All units, charge!"**  (横幅 `[Voice] …` 特写 1 秒)

VO(三段各停一拍,最后一句放慢):
> "I spent a few days building a voice command mod, so you can command your troops by voice and keep your hands on the fight.
>
> I'll walk you through every command, including a few the keyboard can't even give. Then you can give it a try.
>
> It's free. One click on the Steam Workshop."

(字幕:**VOICE COMMANDS. OFFLINE. FREE.** 进标题卡 —— 口径是语音补键盘、不是替代键盘,别用 NO KEYBOARD)

---

## BODY 1 — A real opening, hands-free (0:20–1:50)  ← 主播真实开局流

VO:
> "Let me show you a few commands. This is how I open every battle."

**Step 1 — 弓前步后,散开**(两连喊,每条横幅 1 秒)
> **"Archers, move in front of the infantry."**
> **"Archers, loose formation."**  (校准念不稳就用 **"Archers, spread out."**)

VO:
> "Archers out front, spread out, ready to shoot. Two sentences. My hands never left the reins."

**Step 2 — 分队,各自指挥**(分了必须用,否则等于没演示)
> **"Archers, split."**  → 横幅 `Archers split in two: Left = original, Right = Group 5`

VO:
> "Sometimes I split them. One half is still group two. The other half is now group five. I can move each half on its own."

> **"Group five, go to the right of the infantry."**

VO:
> "'Go to the right of the infantry.' Vanilla has no order for that. You can't park one formation next to another. Here it's a sentence."
> (字幕:**"next to another formation" — not in vanilla**)

**Step 3 — 骑兵去弓箭手左边,或者干脆交给它守**(可选,时长不够就删)
> **"Cavalry, go to the left of the archers."**
> **"Cavalry, guard the left flank."**

VO:
> "Or make it a job. Now they hold that flank, charge anything that gets close, and come back."

**Step 4 — 敌骑射来骚扰,定向打**(等敌骑射逼近弓箭手,镜头先给敌骑射 1 秒)
> **"Cavalry, charge their horse archers!"**
> (横幅特写 `Cavalry → attacking enemy Horse Archers (N)`;慢镜头跟拍骑兵直扑骑射)

VO:
> "Their horse archers always come in to harass us. So I send cavalry after them.
> In vanilla you have to hover the cursor on their formation first. Here I just say who to hit."

> **"Cavalry, attack them!"**  (混战中,骑兵扑向离你最近的那支)

VO:
> "And when I don't know what that unit is called, I say *attack them*. It hits whatever is closest to me."

**Mini-payoff**: 字幕 "That's the opening. Now the part the keyboard can't do."

---

## BODY 2 — The AI layer (1:50–3:20)  ← 最好的点

VO(rehook):
> "Sometimes I push the infantry forward to soak up arrows. But first, let me pull the cavalry back."

> **"Cavalry, fall back."**
> **"Archers, hold the high ground."**  (俯视镜头看弓箭手自己爬坡)

VO:
> "Some of these orders don't exist in the vanilla game. There is no F-key for 'hold the high ground'.
> The game's AI has these behaviors. Only the AI gets to use them.
> This mod lets you call them with your voice."

(可插 3 秒花絮:F6 托管后步弓被合并成一团的实测画面,字幕 "delegation: never again")
VO:
> "Your only option in vanilla is F6 — hand the whole formation over. And when you do, the team AI can merge your infantry and archers into one blob. I learned that the hard way. Here, nothing is handed over."

**Application**(每条一个镜头,横幅特写)
> **"Infantry, advance carefully!"**  (盾墙贴着弓箭手射程慢推。⚠ 必须说 advance carefully,"approach carefully / forward carefully" 试录时没生效)
> **"Cavalry, flank!"**  (骑兵绕大弯抄敌后)
> **"Horse archers, skirmish!"**  (骑射放风筝;念不稳用 **"Horse archers, kite them"**)

VO(收回演示):
> "And the formation is still mine. Watch."
> **"Archers, halt!"**
> "One direct order, and they're back under my control. No delegation. No losing your army to the AI."

**Framing**: "This is the layer the game kept for itself. Now it takes orders."

---

## BODY 3 — The keyboard part, fast (3:20–4:10)

VO(rehook,直接对老玩家的怀疑说话):
> "To be fair, the keyboard is fast for the basics. Some of you saw VoiceAttack do this in 2020: your voice pressed a key. Fine. This does that too. Here's all of it in twenty seconds."

**Formations**(连喊,每条横幅 1 秒,快剪)
> **"Infantry, shield wall."** → **"Infantry, line."** → **"Cavalry, wedge."** → **"Infantry, circle."** → **"Infantry, square."** → **"All units, column."** → **"Archers, scatter."**
> **"Archers, fire at will."** → **"Archers, hold fire."**

**Melee sequence**(骑马冲进去砍,一口气一条,间隔一拍)
VO: "When I ride in myself, I take the cavalry with me."
> **"Cavalry, follow me."**
> **"Horse archers, charge."**
> **"Cavalry, charge their archers."**
> **"Infantry, line."**
> **"Infantry, charge."**
> **"All units, charge!"**

VO:
> "From here my troops fight on their own. I can focus on my own fight."

(花絮 5 秒:"All units" 被听成 "Or unit" 照样冲锋,字幕 "it forgives my accent")

---

## BODY 4 — Setup + three honest things (4:10–5:00)

(屏幕录制配字幕:Subscribe → Mods 勾选 → Play → 两个弹窗 → 选麦克风)

VO:
> "If you tried VoiceAttack back then, you remember the setup: buy it, build a profile, train Windows speech recognition, pray about your accent.
> This is one Workshop subscribe. Link below.
> First launch shows two popups: an *unverified code* warning, because the mod opens a local port; and a UAC prompt, because it presses keys for you. Both are expected.
> Three honest things. One: English support is new. I'm a Chinese streamer; this started as a Chinese mod. Run the calibration once — you read every command out loud and it learns your accent.
> Two: it's better with an NVIDIA card. One click downloads the accurate model.
> Three: it's unlisted for now. I want feedback before I go public."

---

## OUTRO (5:00–5:30)

VO:
> "That's a quick look at what the mod can do.
> Anything you can order with the keyboard, you can now say.
> Plus a few things the keyboard can't do: hold the high ground, advance carefully, attack a specific enemy formation.
> It's still in beta. It's free on the Steam Workshop, link below.
> Try it, and tell me what breaks.
> If you want to see what's coming next, like and subscribe.
> Thanks for watching. See you next time."

(结尾卡:Workshop 链接 + "next: two orders, one breath")
(下期悬念可选加一句:"Next time: 'Archers, come here and loose formation.' Two orders in one breath.")

---

## Recording rules(从 9/7 试录学到的)

- **实况只喊指令,不说话。** 想说话先关识别——0.9.9 起 F12 已取消，用 `control.mode: toggle`（轻点左 Alt 开/关）或 push_to_talk。试录时 "The first one…" 触发了跟随我,"Right." 触发了圆阵。
- **一口气一条指令。** "Horse archer, attack! Horse archer, charge!" 连喊整句作废。
- **兵种用复数**:Archers / Horse archers。指令用词典第一别名。
- 稳步推进只认 **advance carefully**;"approach carefully" 不认,"forward carefully" 会变成普通前进(词典补漏已立待办)。
- 自定义战斗:四兵种齐全,**敌方必须带骑射**,否则 charge their horse archers 没目标。
- 拍前跑一遍英文 **Full run** 校准;念不稳的换别名(loose formation ↔ spread out,skirmish ↔ kite them)。
- 分队槽位号以横幅为准,口播照横幅念。相对站位是一次性移动,骑兵到位后弓箭手别再挪。
- BODY 2 三条战术哪条画面不好就删,不硬拍。

## Speech habits to cut(试录里每句都有)

| 原话习惯 | 改法 |
|---|---|
| So… / like / basically / usually 开头 | 直接主语开头 |
| mod I build | mod I built |
| one of them are in group two | one half is still group two |
| push back their horse archer | drive them off / send cavalry after them |
| absorb some of the arrows | soak up arrows |
| go in to slay some enemies | ride in |
| press 1 to 6 or F1 to 6 | there is no F-key for it |
| help me figure out what's helpful | 删 |
| "it's a beta version" 单独说 | 和 "it's free, link below" 连着说 |

---

## Differentiation vs VoiceAttack(写给你自己,口播只取其中两三句)

| | VoiceAttack(2020 视频) | 这个模组 |
|---|---|---|
| 做什么 | 语音 → 按键宏 | 语音 → 游戏 API(伴侣模组) |
| 能下的指令 | 键盘有的 | 键盘有的 + 定向进攻 / 分队 / 相对站位 / AI 战术层 |
| 识别引擎 | Windows 语音识别,要先训练 | 本地神经网络,开箱即用 |
| 口音 | "我格拉斯哥口音怕不行" | 校准一轮学你的口音;中国主播实测 |
| 说法 | 必须念配置好的原话 | 口语随便说,"go get them" 也认 |
| 反馈 | 无 | 屏幕顶部横幅 + 战斗记录回执 |
| 价格 / 安装 | 付费 + 自己建 profile | 免费,工坊一键订阅 |
| 隐私 | 本地 | 本地,不联网 |

**视频描述里加一行**:"Not a VoiceAttack profile. A companion mod that talks to the game's own formation API — targeting, splitting, relative positioning, and AI tactics that F-keys can't reach."

## Title / thumbnail

- **Title A**: Bannerlord won't let you use half its tactics. So I talk to it.
- **Title B**: Free Bannerlord mod: command your army by voice (keyboard for the simple stuff, voice for the rest)
- **Title C**: "Cavalry, charge their archers" — Bannerlord, hands-free
- **Title D**: Voice-controlled Bannerlord, 6 years later: it's not a macro anymore
- **Thumbnail**: 模组示意图(骑马指挥官喊话 + 声波)+ 两行小写大字,关键词 **voice / FREE**,不用 NO KEYBOARD。生成:`tools/thumb_text.py`。口径:复杂指令一句话说完,键盘留给简单操作。

## Command cheat-sheet(全部已过路由验证)

| Say | Result |
|---|---|
| All units, charge / fall back / advance | 全军冲锋 / 后撤 / 前进 |
| Infantry, shield wall · Archers, spread out · Cavalry, wedge | 阵型 |
| Archers, fire at will / hold fire | 射击控制 |
| Archers, move in front of the infantry · Cavalry, go to the left of the archers [, 30 meters] | 相对站位(需模组,一次性移动,默认 20m) |
| Cavalry, move 20 meters to the right · Archers, fall back 30 meters | 相对自己微调(必须带距离) |
| Cavalry, charge their archers / their horse archers | 定向进攻(需模组) |
| Cavalry, attack them | 就近集火(需模组) |
| Archers, split → Group five, go to the right of the infantry → Archers left, charge | 分队与半队(需模组) |
| Archers, hold the high ground | 占高地 |
| Cavalry, flank | 绕后包抄 |
| Cavalry, guard the left / right flank | 护弓侧翼 |
| Infantry, advance carefully | 稳步推进(只认这个说法) |
| Horse archers, skirmish / kite them | 游击 |
| Archers, halt(或任何直接指令)· Manual control | 从战术收回 |
