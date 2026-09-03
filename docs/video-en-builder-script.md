# English Video Script (builder audience) — "I don't write code. I got an AI to hack a game's brain."

> 受众切换版:主受众是"对用 AI 做游戏模组感兴趣、不写代码的人",骑砍只是本期的案例。
> 结构用 Case Study Explainer(一个可复制的框架,四块)+ But-Therefore 推进;
> 钩子用 Personal Experience + Contrarian;每块结尾一个 payoff;结尾 binge loop 指向下一款游戏。
> 玩家向的旧版脚本保留在 video-en-intro-script.md,以后剪 2 分钟版挂工坊页。
> VO = 英文口播(短句、主动语态);括号里是中文镜头/操作提示。
> ⚠ 关于"不写代码"的措辞:脚本用的是 "I'm a product manager, not a programmer",
>   比 "I can't code" 稳,按你的真实情况调整,这是整支视频的可信度基础。

## Pre-script planning

- **Target audience**: People who've seen "AI writes code" demos and wonder if it works for something real. They may not own Bannerlord. They own *some* game they wish worked differently.
- **Desired emotion**: surprise → "I could do this" (次要:好笑,翻车段)
- **Core promise**: One non-programmer, one AI, one game. By the end you'll know the four moves that turned "I wish this game did X" into a shipped mod — and where it nearly went wrong.
- **Title keyword**: AI game mod / no code
- **Channel promise this sets up**: every episode, a different game, same four moves.

**High-shock facts (惊讶分)**
1. (90) Games have AI layers the player is never allowed to touch. In Bannerlord the enemy general has tactics you can't use. An AI found them by decompiling the game — I just asked.
2. (85) The first time we handed a formation to the game's AI, the game's *team* AI quietly merged my infantry and archers into one blob. The fix was to never hand it over and drive the behavior ourselves, through reflection. I didn't know that word a month ago.
3. (80) The speech engine got swapped three times. A tiny keyword model hit 97% on me and collapsed to 72% on my wife. The final answer was two engines running together: one fast, one accurate.
4. (75) "Charge" kept being heard as "spring breeze" (same sound in Chinese). The fix wasn't training a model. It was letting a text file learn my accent. Cost: zero.
5. (70) Every new command gets replayed against 700+ real recordings of me shouting at the game, to make sure it doesn't steal an old command. The AI built that test harness because it got burned once.
6. (65) Total: a few weeks of evenings. Shipped on the Steam Workshop. Free.
7. (60) I said "infantry, five meters right" as a joke. The AI wrote me an implementation plan. (花絮)

---

## HOOK (0:00–0:20)

**Format**: 效果先行(0~5 秒纯实况确认点击)→ 自我介绍即钩子(Personal Experience + Contrarian)。
定稿顺序:先看军队听话,再认识你;订阅请求挪到第一个 payoff 之后。

(0~5 秒:骑马砍人,不解说,连喊两条,横幅特写)
> **"All units, charge!"** → **"Cavalry, charge their archers!"**

(切到你露脸,或压着战场画面 VO)
> "Hi. I'm a product manager, and I love games.
> I don't write code. But I just built that — a mod that lets me command an army with my voice, including orders the keyboard can't even give.
> I made it to play Bannerlord a new way. I'm sharing it to show what AI can do for modding.
> Let me show you."

(字幕:**PM. NOT A CODER. 0 LINES WRITTEN BY ME.** 进标题卡)

---

## MOVE 1 — Pick a game that can hear you (0:15–1:15)

**Rehook**: "Move one is the one everybody skips, and it's why most 'AI made my mod' videos die on day two."

**Context** (But-Therefore):
> "I stream Bannerlord. Commanding an army needs both hands, *but* you're on a horse. *Therefore* I tried VoiceAttack, the tool everyone used in 2020. It heard my Chinese like a drunk GPS.
> So I asked the AI a product question, not a code question: *what's the shortest path from my voice to this game?*"

**Application**:
> "It came back with a map: microphone → speech model → a matcher → fake key presses. Four boxes. The whole first version was those four boxes, and it worked in a day."

(画面:架构一图流手绘版,四个框;然后第一版黑窗里跑出"步兵盾墙"的实录)

**Framing / payoff**:
> "Move one: don't ask the AI to build the thing. Ask it to draw the shortest path. Then build the boring version first."

**订阅请求放这里**(第一个 payoff 之后,观众刚看到"一天就能跑",转化最好的位置):
> "If you want to see more things like this built with AI — the next one is a different game — subscribe. Now the part where it fell apart."

---

## MOVE 2 — Make it understand *you*, not a robot (1:15–2:30)

**Rehook**: "Day two it worked for me. Day three my wife tried it, and it fell apart. That's where most people quit."

**Context**:
> "The tiny keyword model hit 97% on my voice *but* 72% on hers. *Therefore* we swapped engines. Three times.
> The winner was two engines at once: a fast one that answers in a tenth of a second, and an accurate one that catches what the fast one misses."

(画面:kws/results 的对比数字;"春风"→冲锋的日志截图)

**Application**:
> "And accents? 'Charge' in Chinese kept being heard as 'spring breeze'. Same sound.
> The AI's fix wasn't a bigger model. It was a calibration screen: you read every command once, it writes your mishearings into a text file, and from then on *spring breeze* charges."

(演示:校准界面念一遍,横幅照样出现)

**Framing / payoff**:
> "Move two: the model is not the product. The part that learns *you* is the product. That's a text file."

---

## MOVE 3 — Find what the game hides (2:30–4:00)  ← 最好的点

**Rehook**: "Now the move that made this more than a voice remote. I wanted 'cavalry, charge their archers.' There is no key for that."

**Context**:
> "So the AI decompiled the game. Read the actual code. And found a layer the player is never allowed to touch: every formation has a brain with tactics — hold the high ground, skirmish, guard a flank. The enemy general uses them every battle. You get six F-keys."

(画面:反编译输出滚动,高亮 BehaviorHoldHighGround / BehaviorFlank 类名)

**Application**(战场实录,每条一个横幅特写):
> **"Cavalry, charge their archers!"** — "That's a real lock-on through the game's API."
> **"Cavalry, split!"** → **"Group five, follow me!"** — "Splitting mid-battle. No key for it either."
> **"Archers, hold the high ground!"** / **"Cavalry, protect the left flank!"** — "Those are the game's own tactics. Now they take orders."

**The near-disaster** (But-Therefore, 本段最好的故事):
> "*But* the first version handed the formation to the AI to run those tactics. And the game's *team* AI took that as permission to reorganize my whole army. Infantry and archers, merged into one blob. I couldn't undo it.
> *Therefore* the AI read the game's tick loop and found another way: never hand the formation over. Drive the behavior ourselves, every half second, through something called reflection. The formation stays mine. One direct order snaps it back."

(画面:合并成一团的翻车实录 3 秒 → 修复后按 F1 立刻收回)

**Framing / payoff**:
> "Move three: the best features live in the code the game never exposed. An AI can read it. You just have to ask what's in there."

---

## MOVE 4 — Ship it without breaking it (4:00–5:00)

**Rehook**: "Last move. Everything above is worthless if adding a command silently breaks an old one. It happened. Once."

**Context**:
> "We added 'protect the archers'. It stole 'archers, go there', because the word *archers* was inside the new phrase. Found it by accident."

**Application**:
> "So the AI built a check: every new command gets replayed against 700-plus real recordings of me yelling at the game. Old sentences must route exactly as before. That check now runs before anything ships.
> Then: Workshop upload, bilingual patch notes, calibration for anyone with an accent. It's free and it's live."

(画面:冲突检索输出"真实句变化: 0";工坊页面)

**Framing / payoff**:
> "Move four: keep every real sentence you ever said to it. That pile of recordings is your test suite, and it's worth more than the code."

---

## OUTRO — Binge loop (5:00–5:30)

**Link back**: "Four moves: shortest path, learn the human, read the hidden code, replay reality. Zero lines written by me."

**New problem**: "So the question isn't whether an AI can mod Bannerlord. It's which game is next — and whether the four moves survive a game with no modding API at all."

**Promise**: "Next episode, a different game. Tell me which one in the comments. And if you play Bannerlord, the mod is free on the Workshop, link below."

(结尾卡:下一期游戏投票 + 工坊链接)

---

## Title / thumbnail

- **Title A**: I don't write code. I got an AI to hack a game's brain.
- **Title B**: A product manager, an AI, and one game: we modded what the keyboard can't reach
- **Title C**: 4 moves to build a game mod with AI (no code) — Bannerlord edition
- **Thumbnail**:左半:你的脸 + "PM, not a coder";右半:骑兵冲向弓箭手的画面 + 放大的 `[Voice]` 横幅;大字 **AI BUILT THIS**。封面不写 Bannerlord 字样,游戏名放标题尾部。

## 为什么这样排

- 钩子对准"不写代码的人"而不是骑砍玩家;骑砍画面是证据不是卖点。
- 四个 move 是**可迁移的框架**,下一期换游戏可以复用同一结构,观众会形成"每期四步"的预期。
- 次好在前(引擎/口音),最好在后(读隐藏代码 + 团队 AI 劫持的翻车),完全按留存规则。
- 翻车段是全片的情绪高点:它证明"AI 不是魔法,是要管的",这正是这群受众最想确认的事。

## Pre-flight checklist

- [ ] "不写代码"的措辞按你的真实情况定稿(见文件头)
- [ ] 准备素材:架构手绘图、kws/results 对比数字、"春风"日志截图、反编译滚屏、合并翻车实录、冲突检索"变化: 0"截图、工坊页
- [ ] 战场演示只需 5 条:charge their archers / split + group five / hold the high ground / protect the left flank / 按 F1 收回
- [ ] 战术四条明天实测后再定;效果不好的删,不硬拍
- [ ] 切 English 重启;英文 Full run 校准跑一遍
- [ ] 对镜头说话按 F12 关识别
