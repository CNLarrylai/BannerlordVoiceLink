# English Intro Video Script — "I command my Bannerlord army by voice"

> 定位:面向英文 YouTube 观众的首支介绍/演示视频,4~6 分钟,不讲原理。
> 目标:让老玩家在 20 秒内明白"这解决了骑砍指挥的真痛点",完播后去工坊订阅。
> 说明:VO = 你要念的英文口播(短句,便于非母语念稳);括号里是中文的镜头/操作提示。
> 所有演示指令都用**词典里的第一别名**,是识别最稳的说法。

## Pre-flight checklist(拍摄前,按顺序)

- [ ] 用 v0.9.7 及以上(工坊或本地 [DEV]),启动器切 **English** 后**重启**语音程序
- [ ] 跑一遍 **Full run** 校准(英文,38 条),把你的稳定错听学进个人词典;念不过的指令换别名或从脚本里删掉
- [ ] 自定义战斗:四兵种齐全,敌方带弓箭手 + 骑兵(定向进攻和护翼都要有目标)
- [ ] 浮层开着(观众看识别过程也是内容);对镜头说话时按 **F12** 关识别,防误触
- [ ] 顶部 `[Voice]` 横幅要给特写,它是"真的执行了"的证据
- [ ] 开场别用 "All right, ..." 起手(会被解析成右队);用 "Okay" 或直接喊指令
- [ ] 麦克风电平别太小;录之前喊一句 "All units, charge" 确认横幅出现

---

## ① Cold open(0:00–0:20)不解说,纯实况

(战斗最胶着处,骑马砍人中,双手不离缰绳)

1. 喊 **"All units, charge!"** → 全军冲锋,顶部横幅特写
2. 两秒后喊 **"All units, fall back!"** → 全军后撤
3. 黑屏字幕:**"I didn't press a single key."** → 标题卡

## ② What this is(0:20–1:00)

VO:
> "Bannerlord's biggest lie is that you can command an army with two hands.
> When you're in the saddle, you can't reach F1–F6. So I built a mod that lets me command by voice.
> No cloud, no subscription — it runs on your own PC, and it reacts in about a fifth of a second."

(连喊演示,节奏拉满,每条给横幅 1 秒)
> **"Infantry, shield wall."** → **"Archers, spread out."** → **"Cavalry, wedge."** → **"All units, advance."** → **"Archers, fire at will."** → **"Archers, hold fire."**

(屏幕字幕列出这六句,强调都是自然说法,不是记暗号)

## ③ The stuff the keyboard can't do(1:00–3:30)

VO:
> "Plain orders are the easy part. Here's what the keyboard actually can't do."

**1. Target a specific enemy formation**(定向进攻)
- 喊 **"Cavalry, charge their archers!"**
- 横幅特写:`[Voice] Cavalry → attacking enemy Archers (N)`
- VO: "That's not a simulated cursor. The mod locks my cavalry onto their archer formation through the game's own API."

**2. Focus whatever is in front of me**(看哪打哪)
- 混战中喊 **"Cavalry, attack them!"**
- VO: "In a melee I don't know what that formation is called. I just say *attack them* and it focuses the enemy closest to me."

**3. Split a formation and command each half**(分队)
- 喊 **"Cavalry, split!"** → 横幅:`Cavalry split in two: Left = original, Right = Group 5`
- 喊 **"Cavalry left, charge their archers!"** → 喊 **"Group five, follow me!"**
- VO: "Two cavalry wings, two jobs, one breath. The game only gives you eight slots and no way to split by hand mid-battle."

**4. Tactics — the AI layer**(战术层,重点段)
- VO: "Every formation in Bannerlord has an AI brain with behaviors the player never gets to use. Now I can call them — and the formation stays under my command."
- 喊 **"Archers, hold the high ground!"** → 弓箭手自己走向高地(给一个航拍/俯视镜头)
- 喊 **"Cavalry, protect the left flank!"** → 骑兵站到弓箭手左翼,敌军逼近就自动冲
- 喊 **"Infantry, advance carefully!"** → 步兵盾墙、贴着弓箭手射程推进
- 喊 **"Horse archers, skirmish!"** → 骑射放风筝
- 收回演示:对弓箭手按一下 F1 或喊 **"Archers, halt!"** → VO: "Any direct order takes it back. No delegation, no losing control."

## ④ Setup(3:30–4:30)

VO:
> "Setup is one subscribe."

(屏幕录制,配字幕)
1. Steam Workshop → Subscribe(链接在描述里)
2. Launcher → Mods → tick **Bannerlord Voice Link** → Play
3. "You'll get two popups the first time: an *unverified code* warning, because the mod opens a local port, and a UAC prompt, because it simulates key presses. Both are expected."
4. 主菜单弹出语音面板 → 选麦克风 → 进战斗开喊
5. "If you have an NVIDIA card, click *Download GPU acceleration* once — it switches to the most accurate model."
6. "Run the calibration once. You read every command aloud, and it learns your accent. I'm not a native speaker, and it learned mine."

## ⑤ Honest notes + CTA(4:30–5:30)

VO:
> "Three honest things. One: English support is new — I'm a Chinese streamer, this started as a Chinese mod, so if a phrase doesn't land, the F11 review panel shows you what it heard and you can bind it in one click.
> Two: everything runs offline. Nothing you say leaves your machine.
> Three: it's free. The Workshop link is unlisted for now while I collect feedback, so grab it from the description."

CTA:
> "If you want a command that isn't there yet, tell me in the comments — the dictionary is a text file, adding a phrase takes a minute. And if you're curious how this was built, that's the next video."

(结尾花絮 5 秒:错听名场面,比如 "All units" 听成 "Or unit" 照样冲锋,字幕:"it even forgives my accent")

---

## Title / thumbnail candidates

- **Title A**: I command my Bannerlord army with my voice — and the keyboard can't do half of this
- **Title B**: Bannerlord, hands-free: "Cavalry, charge their archers"
- **Title C**: I gave Bannerlord's AI a voice interface. It listens better than my troops.
- **Thumbnail**: 骑马挥剑的第一人称 + 顶部 `[Voice] Cavalry → attacking enemy Archers` 横幅放大 + 大字 "NO KEYBOARD"

## Command cheat-sheet used in this video(全部已过路由验证)

| Say | Result |
|---|---|
| All units, charge / fall back / advance | 全军冲锋 / 后撤 / 前进 |
| Infantry, shield wall · Archers, spread out · Cavalry, wedge | 阵型 |
| Archers, fire at will / hold fire | 射击控制 |
| Cavalry, charge their archers | 定向进攻(需模组) |
| Cavalry, attack them | 就近集火(需模组) |
| Cavalry, split → Cavalry left, charge → Group five, follow me | 分队与半队(需模组) |
| Archers, hold the high ground | 占高地 |
| Cavalry, protect the left / right flank | 护弓侧翼 |
| Infantry, advance carefully | 稳步推进 |
| Horse archers, skirmish | 游击 |
| Archers, halt(或任何直接指令) | 从战术收回 |

## 拍摄风险提示

- 战术层四条是**明天才实测**的功能,拍之前先按测试清单验一遍;哪条效果不好就从 ③-4 里删掉,别硬拍。
- "skirmish" 是最难念的一个词,校准里过不了就用 **"Horse archers, kite them"**。
- 分队后的槽位号以横幅为准(Group 5 只是示例),口播时照着横幅念。
