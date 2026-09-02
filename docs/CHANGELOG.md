# 更新日志 / Changelog

> 每个版本一节, 中英两段。`tools/release_notes.py` 会把**最上面那个版本**渲染成
> 创意工坊的 Change Notes(写进 tools/steamcmd/item.vdf), 发版前跑一下即可。
> 写给玩家看的: 说"你会感受到什么", 不说"改了哪个函数"。

## 0.9.7 — 未发布

### 中文
- **战术层第二批**(需伴侣模组):占高地(弓箭手占高地)、游击(骑射游击/放风筝)、稳步推进(步兵稳步推进,盾墙贴着弓箭手射程走)、护弓(骑兵保护弓箭手,结圆阵护弓)。都是键盘摸不到的 AI 层,喊"听令"收回。
- **游戏内横幅跟随语言**:英文模式下定向进攻、分队、战术播报全部英文。
- **英文就近集火**:"attack them / get them / kill them / attack the nearest enemy" 现在和中文"打他们"一样,让编队集火离你最近的那支敌军(需伴侣模组);"charge / attack / charge them" 仍是普通冲锋。

### English
- **Tactics, batch two** (companion mod): hold the high ground, skirmish (horse archers kite them), advance carefully (shield wall, stays under archer cover), protect the archers (defensive ring). All reach the AI layer the keyboard cannot; say "manual control" to take back.
- **In-game banners follow your language**: targeted attacks, splits and tactics are announced in English in English mode.
- **Focus fire in English**: "attack them / get them / kill them / attack the nearest enemy" now behaves like the Chinese "打他们": the formation focuses the enemy formation nearest to you (companion mod required). "charge / attack / charge them" remain a plain charge.

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
