# 骑砍语音指挥 (Bannerlord Voice Commander)

中文语音指挥《骑马与砍杀2》军队的软件 + 游戏伴侣模组。作者是游戏主播(中文交流),
目标: 替代 VoiceAttack, 分发给粉丝, 长期拓展多游戏并变现。

## 架构一图流

```
麦克风 → ContinuousListener(VAD断句) → 混合识别 → matcher(模糊+拼音+词序)
                                        │             → Executor(F键注入)
         快路: 流式zipformer+热词(~0.1s)─┤             → ModLink(TCP 35127)
         兜底: faster-whisper(GPU/CPU) ──┘               → 游戏内模组定向攻击
```

- `src/main.py` 主程序(App._handle 是主流水线; --dry-run 冒烟)
- `src/matcher.py` 意图匹配(裁决规则密集, 改前必读其注释, 每条规则都有实战血案)
- `src/stream_asr.py` 快路引擎(峰值归一化0.5必须; 热词=每命令前2别名)
- `src/dictionary.py` 三层词典: commands.yaml + user_aliases.yaml(个人) + fun包(整活)
- `mod/BannerlordVoiceLink/` C#模组(net472, 引用本机游戏DLL, 编译过=API兼容)
- `config/commands.yaml` 词典与键位; `config/settings.yaml` 全部开关
- `kws/` 识别引擎评测工具(bench_stream/bench_accents/colloquial_sweep, 模型已gitignore)

## 铁律 (违反=返工)

1. **版本绝不说谎**: 每次改动部署必须递增 APP_VERSION(src/version.py),
   模组版本=v{APP_VERSION}.{git提交数}, 部署后向用户报版本号。
   tools/build_workshop.py 的预检/最后写戳机制不许绕过。
2. **交付前亲自跑真实入口**: `python src/main.py --dry-run` 看启动横幅,
   编译/单测不够。测试套件: `python tests/run_all.py [--skip-bench]`。
3. **UI 改动后跑 `tools/ui_audit.py`**(双语截断扫描), 新窗口要注册进去。
4. **游戏指令树/键位必须查实**(config/order_tree.yaml 是对照物), 不凭记忆填。
5. **测试用例的单一出处**是 `tests/voice_test_cases.md`(改表会挪题号,
   旧录音要存档)。TTS 语料缓存必须按内容哈希命名, 不许按题号。

## matcher 裁决规则速查 (每条都有回归锁定, tests/test_matcher.py)

- 拼音兜底人人可走取更高分(不设"汉字分低才走"门槛); 整句拼音明显短于
  别名拼音(×1.5)跳过; 对齐丢掉别名否定前缀(别/不/停/收/住)=候选作废。
- tiebreak: 分数 > 解释整句 > 精确出现 > 更长; 同为满分时区间真包含
  对方且更长的赢(功骑兵≠骑兵); 整句==单字别名算精确(喊"冲"是冲锋)。
- 兵种/指令抢同段: 指令多覆盖字=兵种寄生丢兵种; 同段兵种精确=指令让位;
  同段都模糊分差<10=歧义不执行。
- 别名选词: 不用日常聊天词/直播口头禅; 不含其它指令的完整别名;
  不含聊天标记词(这个/那个——永远过不了聊天过滤, 这是"打这只"的由来);
  高频自然话术必须显式收录(出击/回来/集火的教训)。
- 设计取向: **位置指代 > 名字指代**(focus_target"打他们"免疫识别误差)。
- 拼音同音陷阱(2026-09 实测): 别名不含兵种名(含"弓箭手"的别名会抢走"弓箭手去那");
  裸"攻击"禁收(gongji 藏在 弓箭 gongjian 里); 裸"<兵种>左/右"两字禁收(右/游/由/又
  同音, "骑射游击"被抢成右队); "动词+目标"型指令(护弓/进攻X)别名只放动词, 目标走
  takes_target。加新指令前必跑三方向冲突检索(现词典误路由 / usage.csv 真实句
  加入前后 group+order+target 全比 / 新句带各兵种前缀路由), 只比指令不比兵种会漏。

## 战术层(FormationAI)铁律 (2026-09-02 实战血案)

- **绝不 SetControlledByAI(true)**: 一交 AI, 团队 AI 的战术层就接管该编队 —— 合并
  步弓成一队、圆阵套方阵(TacticDefensiveRing)、给骑兵派 ProtectFlank, 挂的特殊
  行为赢不了权重竞争, 玩家还改不回来。"全军占高地"把 8 个队全交出去, 整军被重组。
- 正解=影子驱动(VoiceLinkBehavior.Drive/DriveTick): 反射调 OnBehaviorActivatedAux
  激活一次 + 每 0.5s 替行为 TickOccasionally(行为自己下移动/朝向令), 编队全程
  留在玩家手里; 玩家任何直接指令(OrderController.OnOrderIssued 事件)即停驱动。
- 挑行为类前反编译看 OnBehaviorActivatedAux/TickOccasionally 干了什么, 别按名字猜。

## 识别引擎共识 (数据在 kws/results 与记忆中)

- 快路=sherpa-onnx 流式 zipformer 双语(~70M)+热词+matcher, 真人实测
  90-97%, 换说话人不塌; KWS 3M 已淘汰(声学天花板, 换人塌到72%)。
- Whisper 兜底接快路解不出的(单字词/重口音); 混合=两全。
- 模型对麦克风电平敏感→stream_asr.transcribe 里峰值归一化到0.5(0.9会过)。
- TTS 口音评测(bench_accents 6声线)只信"跨声线系统性失败", 单条伪影不追。
- 长期路线: 语音数据共建(donation.py)攒语料 → icefall 微调小模型
  (就绪线: ≥3000条/≥10说话人/常用指令各≥100, tools/ingest_donations.py 看进度)。

## 平台与部署

- **Windows 台式机 = 游戏机**: 打包(PyInstaller app.spec)、部署
  (tools/build_workshop.py → 游戏 Modules, 预检要求游戏/语音程序全关)、
  模组编译(dotnet build, 引用 C:\Program Files (x86)\Steam 下游戏DLL)只能在这做。
- **Mac = 纯开发**: matcher/词典/测试(纯逻辑部分)/文档可改; keyboard/
  pydirectinput/模组编译不可用; 改完推回来在 Windows 机验证+部署。
- 用户数据在 %LOCALAPPDATA%\BannerlordVoice\(个人词典/usage/共建录音/日志),
  不进仓库; 日志 app.log, 模组心跳 mod.log, 每条识别 usage.csv(黑窗日志
  有"不落盘之谜", usage.csv 才是可靠数据源)。
- 排错流程: 用户从启动器测, 报问题看 app.log 最后一个"新会话"段落 + mod.log
  心跳三行 + usage.csv 尾部。

## 当前状态 (2026-09-02)

v0.9.6 已上工坊(ItemID 3775571491, Unlisted)。发版四步见 mod/PUBLISH.md:
build --release → 写 docs/CHANGELOG.md(中文+English) → tools/release_notes.py
→ steamcmd 上传(登录态已缓存)。用户要求每版说明都中英双语, 由 AI 起草。
教训: 打包版查 HF 缓存曾写死 Systran 仓库名, turbo(mobiuslabsgmbh)永远"未下载"
静默回退 small —— 凡"模型解析"必须走 models.model_repo 映射并用假 _MEIPASS 测。
英文模式: 占比/杂字按词算; 短句对长别名 partial_ratio 按长度比打折; 口音别名
(or/oh units)进词典; 测试模式(listen.py)不走快路/重试, 与真实模式有差异(待收敛)。

## 历史状态 (2026-07-10)

v0.8.0(游戏1.4.7): 混合识别/指令复盘(F11)/语音数据共建/整活词典(fun.pack)/
游戏内双通道通知(顶部横幅+左下记录)/**分队**(骑兵分队→左队进攻/右队跟我,
原生Formation.Split, 左右按玩家视角朝向)。
分队的左右手性(叉积符号)是**部署后待实测**项 —— 若左右喊反, 翻 DoSideOrder
里 `(ca >= cb) == wantLeft` 的符号即可。
待办: 分队左右实测; 创意工坊上传(差用户跑上传命令+宣传图); B站第一期视频
(脚本 docs/video-ep1-script.md); 英文快路热词; 语料攒够后微调小模型。

## 路线图 (用户 2026-09-03 定)

1. **长句/组合指令**: "Archers, come here and loose formation" —— 整句先试, 不过再按
   连接词(and/then/,/然后/再)切段各自解析, 后段继承前段兵种, 全部段解析成功才按序执行
   (有一段是聊天整句不发)。含 and 的固定别名(hit and run)先整体匹配。
2. **用户自定义指令更灵活**: 现在只能给已有指令加说法(个人词典/整活包); 目标是让
   玩家自己定义新指令(键序列/模组动作组合), 不改代码。
3. **相对站位/位置微调**: 语法 `A(队伍) 去 B(队伍) 的 C(方位) [D(距离)]` —— A 省略=当前
   选中; B 省略=A 自己(即"往右 20 米"); C=左/右/前/后, 以 B 朝敌方向为准(不是屏幕);
   D 默认 20m。中文方位词在目标之后, matcher 需支持带占位的模板别名(去{目标}右边);
   模组侧一次性 MovementOrderMove, 不持续驱动。

## 多会话并行 (git worktree, 2026-09 起)

```
C:\Users\Victoria\bannerlord-voice              main       集成 / 识别链路 / 部署 / 发版 (唯一有权写 Modules 与上传工坊)
C:\Users\Victoria\bannerlord-voice-wt\matcher   wt/matcher 词典 + matcher + 回归用例
C:\Users\Victoria\bannerlord-voice-wt\mod       wt/mod     C# 模组 (dotnet build 独立编译)
C:\Users\Victoria\bannerlord-voice-wt\ui        wt/ui      UI/UX: 窗口文案 i18n / 布局 / 浮层提示 (不碰识别与匹配逻辑)
```
- 每个 worktree 开自己的 Claude 会话; 新增: `git worktree add ../bannerlord-voice-wt/<名> -b wt/<名>`。
- worktree 里没有 .venv 和 kws/models(gitignore): 跑测试用主目录的解释器
  `C:\Users\Victoria\bannerlord-voice\.venv\Scripts\python.exe tests\run_all.py --skip-bench`;
  需要麦克风/GPU/快路/部署的活只在 main 做。
- 合并门槛(谁改谁跑): run_all --skip-bench 全过 + 涉及窗口的 ui_audit.py 无截断 +
  涉及模组的 dotnet build 过 + 改词典的跑三方向冲突检索。过了才 merge 进 main。
- 跨会话共识写这里, 不写某个会话的记忆。

## GitHub (跨机器同步)

私有仓库 github.com/CNLarrylai/BannerlordVoiceLink, origin/main。
开工前 git pull, 收工 git push。部署只在 Windows 游戏机。
积累新教训时同步更新本文件(不只更新某台机器的记忆), 否则另一台掉队。
