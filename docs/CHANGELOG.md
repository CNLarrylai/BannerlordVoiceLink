# 更新日志 / Changelog

> 每个版本一节, 中英两段。`tools/release_notes.py` 会把**最上面那个版本**渲染成
> 创意工坊的 Change Notes(写进 tools/steamcmd/item.vdf), 发版前跑一下即可。
> 写给玩家看的: 说"你会感受到什么", 不说"改了哪个函数"。

## 0.9.7 — 2026-09-09

### 中文
- **重要修复:模型下载**。原先依赖的 hf-mirror 镜像已关站,导致音频设置里"需联网下载"的模型谁都下不了。现在按顺序自动试 HuggingFace 官方 → 镜像 → **魔搭 ModelScope(国内直连可用)**,哪个通用哪个;都不通时会明确告诉你怎么办(挂代理,或把模型文件夹放到 `%LOCALAPPDATA%\BannerlordVoice\models\<模型名>\`)。
- **GPU 加速库下载提速**:下载前并行测速各个源,谁快用谁。原先固定国内镜像优先,海外或挂代理的机器只有 2 MB/s,现在能跑满带宽。
- **战术层第二批**(需伴侣模组):占高地(弓箭手占高地)、游击(骑射游击/放风筝)、稳步推进(步兵稳步推进,盾墙贴着弓箭手射程走)、护翼(骑兵保护左翼/右翼:站到弓箭手侧翼不挡射线,有敌军逼近就打,退开归位;"骑兵保护弓箭手"自动选离敌近的一侧)。这些是键盘摸不到的 AI 层,但部队**不交给 AI 托管**、始终归你指挥,对它下任何直接指令就自动停。
- **相对站位 / 位置微调**(需伴侣模组):"骑兵去弓箭手右边""步兵到骑射前面三十米""骑射往后退五十米";英文 "Cavalry, go to the right of the archers""Infantry, move 20 meters to the right"。左右按你的视角、前后按朝敌方向,默认 20 米;一次性移动令,随时可改。护卫目标也放开到任意己方兵种(骑兵保护骑射)。
- **第 5~8 队与左右半队支持全部指令**:阵型、射击、上下马、战术、站位都能对"第六队""骑兵左队"下达,不再只有六条派遣令。
- **英文就近集火**:"attack them / get them / kill them / attack the nearest enemy" 和中文"打他们"一样,让编队集火离你最近的那支敌军(需伴侣模组);"charge / attack" 仍是普通冲锋。
- **游戏内横幅跟随语言**:英文模式下定向进攻、分队、战术播报全部英文。
- **启动器按使用顺序重排**:① 音频与模型设置(没选麦克风时高亮提醒)→ ② 跟读练习(可选)→ 开始语音指挥(旁边是小号的测试模式)→ 玩过之后再看的指令复盘 / 指令词典。
- **首次打开跟随系统语言**:中文 Windows 默认中文,其它系统默认英文;之后你在启动器里切过的语言一直保留。
- **跟读练习升级**:默认「完整练习」按当前词典生成题库,把支持的全部指令(含分队、左右队、第N队、战术层)各念一遍,约 6 分钟;原来的常用指令模式保留为「快速」。每条录音附带标注,勾选"语音数据共建"后导出会一起带上。
- **模组在游戏启动器里改名为 Voice Commander**,与工坊页一致;新封面。

### English
- **Important fix: model downloads**. The hf-mirror site we relied on shut down, so any model marked "needs download" failed for everyone. Downloads now try HuggingFace → mirror → **ModelScope (reachable from mainland China)** in turn, and if nothing works you get a clear next step (use a proxy, or drop the model folder into `%LOCALAPPDATA%\BannerlordVoice\models\<model>\`).
- **Faster GPU library download**: sources are speed-tested in parallel before downloading and the fastest wins. It used to pin a China mirror first, which crawls at ~2 MB/s from abroad or through a proxy.
- **Tactics, batch two** (companion mod): hold the high ground, skirmish (horse archers kite them), advance carefully (shield wall, stays under archer cover), protect the left/right flank (cavalry holds the archers' flank without blocking their line of fire and engages anything closing in; "protect the archers" auto-picks the side nearer the enemy). All reach the AI layer the keyboard cannot, without delegating the formation to the AI: it stays yours, and any direct order stops the tactic.
- **Relative positioning** (companion mod): "Cavalry, go to the right of the archers", "Infantry, move in front of the horse archers, 30 meters", "Horse archers, fall back 50 meters". Left/right follow your camera view, front/back follow the enemy direction; default 20 m; a one-shot move order you can override any time. Guarding now works for any friendly formation ("cavalry, protect the horse archers").
- **Groups 5-8 and split halves take every order**: formations, fire control, mount/dismount, tactics and positioning all work for "group six" / "cavalry left", not just the six basic orders.
- **Focus fire in English**: "attack them / get them / kill them / attack the nearest enemy" now behaves like the Chinese "打他们": the formation focuses the enemy formation nearest to you (companion mod); "charge / attack" stays a plain charge.
- **In-game banners follow your language**: targeted attacks, splits and tactics are announced in English in English mode.
- **Launcher reorganized in the order you actually use it**: ① Audio & Model Setup (highlighted until you pick a mic) → ② Practice (optional) → Start Voice Command (with a small Test Mode beside it) → Review / Commands for later.
- **First launch follows your system language**: Chinese Windows starts in Chinese, everything else in English; whatever you pick in the launcher afterwards sticks.
- **Practice upgraded**: the default "Full run" builds its drill from the current dictionary, so you read every supported command once (splits, halves, numbered groups and tactics included, ~6 min); the old common-commands mode stays as "Quick". Each recording is labelled and travels with a voice-data donation export.
- **The mod is now named Voice Commander in the game launcher**, matching the Workshop page; new cover art.

## 0.9.6 — 2026-09-02

### 中文
- **重要修复**:选了 large-v3-turbo 模型,实际一直在跑 small。打包版找模型缓存时仓库名写错,导致音频设置里选 turbo、或 GPU 引导装完 turbo 之后都静默回退。现已修复,N 卡玩家会真正用上最准的模型。
- **英文识别加固**:非母语口音把 "All" 说成 "Or/Oh" 也能命中;英文的"是不是指令"判定改按词算,短指令不再被当聊天丢掉;"Or." "Oh." 这类噪音短句不再误触阵型。
- **手动放模型**:模型文件可直接放到 `%LOCALAPPDATA%\BannerlordVoice\models\<模型名>\`,免手搓缓存路径。国内下载教程见讨论区。

### English
- **Important fix**: selecting large-v3-turbo actually kept running small. The packaged build looked up the model cache under the wrong repository name, so choosing turbo in Audio Settings (or after the GPU setup wizard) silently fell back. Fixed; NVIDIA users now really get the most accurate model.
- **English recognition hardened**: non-native "All" heard as "Or/Oh" still lands on all units; the "is this a command" check now counts words instead of letters so short orders are no longer dropped as chatter; noise fragments like "Or." / "Oh." no longer trigger formations.
- **Manual model folder**: drop model files into `%LOCALAPPDATA%\BannerlordVoice\models\<model>\` and they are picked up directly.

## 0.9.3 — 2026-08-17

### 中文
- **识别**:默认模型按算力自动分档。无显卡也有满命中(small 内置,免下载),有 N 卡自动用最强档;老用户的默认档位也会自动升级。
- **国内**:模型与 GPU 加速库改走国内镜像并支持断流自动换源,不再需要梯子。
- **新功能**:分队(骑兵分队 → 骑兵左队进攻 / 第五队跟我)、绕后战术(骑兵绕后,指挥到键盘摸不到的 AI 层)、定向进攻状态播报。
- **体验**:N 卡玩家首次启动会引导一键启用 GPU 加速;新增一键打包日志;修复"全军出击"等口语误触发。

### English
- **Recognition**: default model now scales with your hardware. Full accuracy even without a GPU (small is bundled, no download); NVIDIA users automatically get the top tier; existing users are upgraded too.
- **China**: models and CUDA libraries download through domestic mirrors with automatic failover.
- **New**: split formations (cavalry split → cavalry left charge / group five follow me), flanking tactic (reaches the AI layer the keyboard cannot), in-game feedback for targeted attacks.
- **Quality of life**: first-run GPU setup wizard for NVIDIA users; one-click log bundle for bug reports; fixed false triggers on colloquial phrases.

## 0.8.7 — 2026-08-01

### 中文
- 首次上传创意工坊。

### English
- First Workshop upload.
