# HANDOFF — BannerlordVoiceLink（骑砍语音指挥 / Voice Commander）

> 更新：2026-10-09 01:25 Sydney · 写的人：Claude Code（Opus 5.5，main 会话，只读 review + 换行符清理）
> 接手者先读本文件，再读共享仓库 `agent-memory/projects/bannerlord-voicelink.md`；动手前读「建议加载」里的 skill / lessons。

## 现在在做什么（一句话）
线上最新 v0.9.10（2026-09-25）；`wt/slim` 有一个未合并、未发版的 v0.9.11（包体瘦身）；主目录有一批英文视频/封面素材未提交，等 Larry 定 commit 分组。

## 下一步（接手者直接执行，1–3 条）
1. 等 Larry 点头后按分组提交主目录改动（清单在本次会话回复里：`.gitattributes`+CLAUDE.md / 封面工具链 / 英文视频文档 / 素材图）；`config/settings.yaml` 的 `language: en` **不提交**，保留还是 `git checkout --` 恢复 zh 由他定。
2. `wt/slim` 合并前：在 slim 里补 `src/audio_setup.py` 的 `_effective`/`models.is_ready` → 改用 `stt.resolve_stt_config` + `stt.model_available`（否则打包版选 auto 会提示「base 未下载」、装了 small 也显示 base）；然后跑 `run_all --skip-bench` + `tools/ui_audit.py`。
3. 合并后发版前必须真打包：核实整包实际体积（commit 里的 615MB 是「预计」）、跑打包版 `--dry-run`、`tools/fresh_user.py` 模拟无卡新用户首启弹 AccuracyOfferDialog；CHANGELOG 0.9.11 日期改成发版日。

## 刚做完、已验证的
- 新增 `.gitattributes`（`* text=auto eol=lf`，bat/cmd/ps1/sln 保留 CRLF）；CLAUDE.md 磁盘文件改回 LF。`git diff --stat`：CLAUDE.md 398 行 → 7 行（交接协议 6 行 + slim 一行），settings.yaml 280 行 → 2 行（只剩 language）。`git status` 无其它文件因规范化变脏。
- CLAUDE.md worktree 表补了 `wt/slim`。
- 读完 `0d41976` 全 diff：父提交 = main HEAD `aff0434`，可快进，与主目录未提交改动无文件重叠。

## 卡住的 / 没验证的 / 待 Larry 决定的
- **wt/slim 测试本会话没跑成**：非交互权限拦了 python 调用。commit message 自称 run_all 全过 + ui_audit 无截断，未复核。
- 工坊线上版本号未核（https://steamcommunity.com/sharedfiles/filedetails/changelog/3775571491）。
- `docs/video-en-intro-script.md` 的录制规则还写「想说话先按 F12 关识别」——F12 静音在 0.9.9 已取消（CHANGELOG 0.9.9），要改成按键开关模式。
- `docs/_review-result-2026-10-09.md` 是空文件、`_review-brief` 是给本会话的任务书：都不入库。
- 分队左右手性实测、误建空壳工坊条目 3775583505 是否已删：仍无记录。
- 魔搭/国内下载：等真实国内用户反馈。

## 已否决的方案与原因（最重要——版本库里查不到）
- **绝不 `SetControlledByAI(true)`**（2026-09-02 实战）：团队 AI 接管编队、整军被重组；正解影子驱动 `VoiceLinkBehavior.Drive/DriveTick`。
- 别用 `QuerySystem.MainClass` 判兵种（15 s 缓存），用 `GetCountOfUnitsBelongingToPhysicalClass`。
- turbo 不能当无 CUDA 默认（CPU 6.2s）；0.9.11 起 small 也不再是无卡默认（不内置，auto=已下载才用 small，否则内置 base）。模型解析走 `models.model_repo`，判断「要不要下载」用 `stt.model_available`，别用 `models.is_ready`（看不见内置进包的模型）。
- hf-mirror / `snapshot_download` 国内卡死不报错——已换自写多源测速下载器；用 `tools/cn_check.py`。
- TaleWorlds 官方上传工具在此机必挂，只能 SteamCMD；steamcmd 登录会把 Steam 客户端顶下线。
- 别名：裸「攻击」禁收；别名不含兵种名；「动词+目标」只放动词；分差线 10 别动。
- 工坊 previewfile 不再由 `make_workshop_art.py` 覆盖，改由 `tools/make_cover_painted.py`（底图 `assets/art/cover_base_2048.jpg`）生成，已在 `7881f15` 提交过。

## 谁在等我
- Larry：主目录 commit 分组、settings.yaml 语言、wt/slim 合不合。
- YouTube 报 archers/cavalry 反了的用户是否已被告知 0.9.10 修复 — 未知。

## Larry 的口头约定（没进需求文档的）
- 2026-09-02：每版更新说明由 Agent 起草中英两段；上传前须他明确说「发」；Change Notes 发出不可编辑，先 `--preview`。
- 2026-09-09：优先 CLI，不要截图/模拟点击。

## 别碰的
- **主目录（main）是唯一有权写 Modules、部署、上传工坊的地方**；worktree 只写代码：`-wt/matcher`、`-wt/mod`、`-wt/ui`、`-wt/slim`（包体瘦身 v0.9.11）。worktree 无 .venv，测试用主目录解释器。
- `config/settings.yaml` 是被跟踪的开发机配置（麦克风/turbo/语言都是本机值），发版时 `build_workshop.py` 临时净化成发行默认——别手动「修」成发行值再提交。
- `user_aliases.yaml`（gitignored）；`tools/steamcmd/item.vdf` 的 ItemID 3775571491 不改。

## 关键入口
- 跑起来：`run.bat` → Hub；干跑 `python src/main.py --dry-run`
- 测试：`python tests/run_all.py --skip-bench`；UI `tools/ui_audit.py`；日志 `%LOCALAPPDATA%\BannerlordVoice\logs\app.log` / `mod.log`
- 发版：`mod/PUBLISH.md` 四步

## 建议加载
- skills：handoff
- lessons：`agent-memory/lessons/windows-tooling.md`、`agent-memory/lessons/verification.md`

---
规则：≤60 行。停手前在一个能说清的断点覆写本文件。不重复 spec / CHANGELOG / commit 里已有的内容，给路径。不写凭据。
