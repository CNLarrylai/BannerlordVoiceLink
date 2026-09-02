# 创意工坊发布指南 (整包分发: 模组 + 语音程序)

## 这个包是什么

订阅者一次拿到全部, **零配置起步**:

```
Modules/BannerlordVoiceLink/            (~397 MB, 工坊对大模组很宽容)
├─ SubModule.xml
├─ bin/Win64_Shipping_Client/BannerlordVoiceLink.dll   ← 游戏内模组(锁定敌方编队)
└─ VoiceApp/                                            ← 完整语音程序
   ├─ BannerlordVoice.exe                               (启动器 Hub)
   └─ _internal/  (含内置 base 模型, 免联网可用; 配置=发行默认)
```

**订阅者体验**: 订阅 → launcher 勾选模组 → 开游戏(点掉"未验证代码"和 UAC 两个
弹窗) → 到主菜单时**语音面板自动弹出** → 选麦克风 → 进战斗开喊。
配置写在用户自己的 %LOCALAPPDATA%\BannerlordVoice, 更新模组不会覆盖。

- 自动启动逻辑在模组里: 已在运行/未随包/存在 `VoiceApp\autostart_off.txt` 则跳过。
- 心跳日志: %LOCALAPPDATA%\BannerlordVoice\logs\mod.log (排错先看这里)。

## 构建 (每次发版)

```
.venv\Scripts\python tools\build_workshop.py        # 全量: DLL + EXE + 组装 + 体检
.venv\Scripts\python tools\build_workshop.py --skip-exe   # 只更新模组 DLL
```

体检会硬校验: 三件套齐全 + 随包配置必须是发行默认(麦克风 null / model auto /
中文) —— 你的本机设备名和模型选择不会被打进包里。

## 发版流程 (SteamCMD, 2026-08 起; 官方 TaleWorlds 工具在本机会 "Timeout uploading manifest")

ItemID 3775571491 (Unlisted)。每次发版四步:

```
.venv\Scripts\python tools\build_workshop.py --release     # 1. 正式构建(去掉 [DEV] 名)
# 2. 在 docs/CHANGELOG.md 顶部写新版本一节(中文 + English 两段)
.venv\Scripts\python tools\release_notes.py               # 3. 渲染成工坊 Change Notes -> item.vdf
cd tools\steamcmd
.\steamcmd.exe +login linghualai +workshop_build_item "C:\Users\Victoria\bannerlord-voice\tools\steamcmd\item.vdf" +quit   # 4. 上传
```

- 构建前关掉: 打包版语音程序(管理员权限, 用 stop_all.bat)、骑砍 launcher / 游戏。
- 首次登录要输密码 + Steam Guard, 之后 steamcmd 会缓存登录态, 一般不再问。
- Change Notes 支持 BBCode; release_notes.py 输出的是 [h2]/[h3]/[list], 中英各一段。
- 上传成功后到工坊页 Change Notes 标签核对:
  https://steamcommunity.com/sharedfiles/filedetails/changelog/3775571491

## 诚实注意事项

- **两个弹窗是常态**: 游戏启动时的"未验证代码"(模组用了网络socket, 必然被标) 和
  语音程序的 UAC 提权(发按键需要) —— 工坊简介里提前说明, 减少差评。
- 订阅者的杀软可能对 PyInstaller exe 误报 —— 简介里注明开源/可自行编译可减压;
  以后上代码签名证书可根治。
- 工坊订阅的模组在 steamapps\workshop\content\261550\<ItemId>\, 不在游戏 Modules;
  模组按自身 DLL 位置找 VoiceApp, 两种位置都能工作(已按此设计)。
- 你自己本机的 Modules\BannerlordVoiceLink 是"开发版"; 如果同时订阅了工坊版,
  launcher 里只勾一个, 避免双份加载。
- 游戏大版本更新后: 重编模组(体检会暴露 API 变化), 更新 WorkshopUpdate.xml 里的
  Compatible Version 标签。

## 参考

- 官方上传文档: https://moddocs.bannerlord.com/steam-workshop/uploading_updating_mod/

## ⚠ 本机实测: TaleWorlds 上传工具不可用, 用 SteamCMD

TaleWorlds.MountAndBlade.SteamWorkshop.exe 在本机稳定复现
"Timeout uploading manifest"(换区/重启/多次重试均无效), 已改用 SteamCMD
(独立连接栈, 2026-08-02 实测成功, ItemId 3775571491):

```
cd C:\Users\Victoria\bannerlord-voice\tools\steamcmd
.\steamcmd.exe +login <用户名> +workshop_build_item "C:\Users\Victoria\bannerlord-voice\tools\steamcmd\item.vdf" +quit
```

- 以后每次更新: 先 build_workshop.py 打包, 再跑上面命令(改 item.vdf 的 changenote)
- 登录要输密码+Steam Guard(本人操作)
- 元数据(简介/图片/可见性)在工坊网页上改即可, 不必走命令行

## 开发版/工坊版命名区分 (2026-08-02 起)

- 默认构建给模组名字盖 [DEV] 戳: launcher 里显示 "Bannerlord Voice Link [DEV]",
  与工坊订阅版一眼区分, 防止勾错。
- **上传工坊前必须**: `build_workshop.py --release` 重新组装(干净名字), 再跑
  SteamCMD 上传; 传完想继续开发, 再跑一次不带 --release 的构建即可。
