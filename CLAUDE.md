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
  不进仓库; 日志 app.log, 模组心跳 mod.log, 每条识别 usage.csv。
- **AI 工具进程看到的 %LOCALAPPDATA% 是假的**(2026-09-09 查明, 即所谓"日志不落盘之谜"):
  Claude 桌面版是 MSIX 包, 它拉起的终端/python 对 AppData 的**写入被重定向到**
  `%LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Local\`, 读取是"影子层+真实
  目录"的合并视图, 同名文件影子层优先。后果: 从工具里热拷 commands.yaml / 改 settings /
  改名数据目录全落在影子层, 成品包(容器外)看不见; 之后读日志读到的是影子层的旧文件。
  规矩: 工具里**只读不写** %LOCALAPPDATA%\BannerlordVoice; 必须写就走容器外进程
  (`tools/fresh_user.py` 里的 `run_outside()`: WMI Win32_Process.Create 起的进程没有包
  身份, 写真实目录); 读到的日志时间对不上时先 `os.path.realpath` 看是不是影子层。
  `~/.cache/huggingface` 不在 AppData, 不受影响。
- 排错流程: 用户从启动器测, 报问题看 app.log 最后一个"新会话"段落 + mod.log
  心跳三行 + usage.csv 尾部。
- 模拟新用户: `tools/fresh_user.py start|restore|status`(藏起数据目录与 HF 模型缓存,
  可逆不删)。2026-09-09 首测即抓到: hf-mirror.com 已变 308 跳转, 模型下载必失败。

## 当前状态 (2026-09-09)

v0.9.7 已上工坊(ItemID 3775571491, Unlisted; 模组显示名 Voice Commander, 新封面)。
本版要点: 战术层第二批 / 相对站位 / 5~8 队与半队全指令 / 模型下载改多源回退(hf.co →
镜像 → 魔搭, HF 系先 4s 探通) / CUDA 库下载并行测速 / 首启跟随系统语言 / 启动器分步重排。
待办: 工坊简介双语化; 魔搭这条路等真实国内用户反馈; 若不稳再考虑把 turbo 打进包(+1.6GB)。
发版四步见 mod/PUBLISH.md:
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
   选中; B 省略=A 自己(即"往右 20 米"); C=左/右按**玩家视角**(镜头朝向, 与分队左右
   一致; 按编队朝向算会随弓箭手转身而变, 实测不可预判), 前/后按朝敌/背敌;
   D 默认 20m。中文方位词在目标之后, matcher 需支持带占位的模板别名(去{目标}右边);
   模组侧一次性 MovementOrderMove, 不持续驱动。

## 视频/封面素材工具 (2026-09)

- 抠图: `.venv` 里已装 **rembg 2.0.84 + onnxruntime**(2026-09-09), 人像模型
  `u2net_human_seg` 已下载到 `~/.u2net/`, 以后抠头像直接用, 不用再装/下载。
  经验: 先把源图紧裁到人物(把椅子/杂物裁出画框), 再 `remove(..., session=new_session("u2net_human_seg"), post_process_mask=True)`;
  人像贴画面右/下边缘让切边落在画框外; 白描边 = alpha 膨胀(MaxFilter)后填白。
- 封面加字: `tools/thumb_text.py`(1280×720, `*词*` 黄色, `|` 分行, --style round/shout, --top 裁剪起点, --align)。
- 喊话封面(自拍抠图镜像+声浪): `tools/make_thumb_shout.py`(rembg 抠图→镜像朝左贴右侧, 白描边+投影,
  嘴部发出声波弧/射线/弱光锥, 以嘴为中心的缩放模糊给冲击感; `--base knight|field`,
  field 是把大军底图整张左右翻转好让声波从右往左扫; `--cache` 存抠图结果避免重抠)。
  经验: 白描边要求人像 alpha **不贴自己的包围盒边**(贴边=压出一条直线), 所以先四周补透明边,
  且被画框裁断的那侧(身体下缘)必须留在画外; 底图自带的 UI 面板只能靠渐变压暗+模糊盖掉。
- 成片叠指令注释卡 + YouTube 规格重编码: `tools/annotate_video.py`(转写定位指令, NVENC cq20, 音频 remux)。
- 素材目录: 视频/封面产物在 `H:\2025录制\粗剪_语音指挥\剪映初稿\`; 模组宣传图在 `assets/art/`。
- 文案: `docs/youtube-upload-kit.md`(标题/描述/标签/上传设置), `docs/nexus-description.md`。
  口径: 语音补键盘不替代键盘; 不用 "voice mod" 连写(会命中 Voicemod 破解搜索), 统一 voice command。

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
