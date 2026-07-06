# 骑砍语音指挥 (Bannerlord Voice Commander)

用**中文语音**指挥《骑马与砍杀2：霸主》的军队。本地 Whisper 识别 + 同义词模糊匹配 + DirectInput 按键，比 VoiceAttack 更灵活、中文更准、直播更好看。

## 特点

- 🎙 **本地中文识别**：faster-whisper（GPU 加速），离线、低延迟、无按次费用。
- 🧠 **灵活匹配**：一句指令多种说法都能命中，说多了/漏字也认（rapidfuzz 模糊匹配）。
- ⚙️ **全配置化**：所有兵种编号、指令说法、键位都在 `config/` 的 YAML 里，改它不用碰代码。
- 📺 **直播浮层**：置顶小窗实时显示"识别到的指令"，观众一看就懂。
- 🎮 **DirectInput 注入**：专门适配骑砍这类 DX 游戏（普通模拟按键经常无效）。

## 安装

需要：Windows + Python 3.10+（已测 3.13）+ NVIDIA 显卡。

```
双击 setup.bat        （创建虚拟环境并装好所有依赖，第一次较慢）
```

## 使用

**双击桌面「骑砍语音指挥」图标**（金色令字），打开启动器 Hub，里面四个功能：

| 按钮 | 作用 |
|---|---|
| ▶ 开始语音指挥 | 正式版：识别→发按键，进游戏用（自动请求管理员） |
| 🎧 测试模式 | 只听不发键，安全调试麦克风/识别 |
| 🎙 音频设置 | 选麦克风、看实时音量条 |
| 📖 指令词典 | 看/加说法、改键位（改完按 F10 热重载） |

1. 点「开始语音指挥」，弹出黑窗加载 Whisper 模型（第一次会自动下载，需联网）。
2. **默认持续监听**（像 VoiceAttack）：开着就一直听，说出指令自动识别并执行，没匹配的继续听，全程不用按键。
3. 屏幕左上角浮层显示识别结果；OBS 里用窗口捕获 + 色键可抠掉背景。
4. 改了词典后，在语音黑窗里按 **F10** 热重载，不用重启。

> 启动器已设为管理员运行（注入按键需要），子功能都由它拉起。
> 命令行党也可直接 `run.bat` / `run_listen.bat` / `run_audio_setup.bat` / `run_commands.bat`。

### 两种模式（在 `settings.yaml` 的 `control.mode` 切换）

- `continuous`（默认）：一直监听，VAD 自动断句。
- `push_to_talk`：按住热键（默认 `Caps Lock`）说话，松开识别。嘈杂环境更稳。

### 直播防误触：口令前缀（强烈推荐）

持续监听时，你跟观众聊天也会被识别。在 `settings.yaml` 里设置：

```yaml
control:
  command_prefix: ["传令", "听令", "下令"]
```

设置后，只有先说前缀才会执行，例如说"**传令，弓箭手散开**"才发指令，平时聊天不会误指挥军队。留空 `[]` 则是纯 VoiceAttack 式（听到任何指令都执行）。

### 测试（可量化追踪）

```
双击 run_tests.bat          （匹配回归 + 识别命中率/延迟基准）
```
改了词典/键位/模型后跑一下，用数字确认有没有变好或变坏；识别结果会追加到
`tests/results/history.csv`。详见 [tests/README.md](tests/README.md)。

## 配置

- `config/settings.yaml`：模型、麦克风、热键、阈值、按键间隔、浮层开关。
- `config/commands.yaml`：**核心词典**。
  - `groups`：兵种 → 编队数字键（按你的布阵顺序改）。
  - `orders`：指令 → F 键序列（按你游戏里实际的指令菜单核对）。
  - 每项的 `aliases` 是多种说法，想加新说法直接往里加。

### ⚠️ 第一次必做：校准键位

`commands.yaml` 里的 F 键序列是按骑砍默认指令菜单填的参考值。请进游戏对着指令轮盘核对：
- 编队数字（1~8）要对应你实际的兵种顺序。
- 每条指令的 F 键路径要和你游戏里的菜单一致，不一致就改 `keys`。

校准列麦克风设备：`py -m sounddevice`（把编号填到 settings 的 `audio.device`）。

## 结构

```
config/      settings.yaml + commands.yaml  (配置, 改这里)
src/         main / launcher / audio / stt / matcher / executor / overlay / *_gui
tests/       corpus.yaml + 匹配回归 + 识别基准 + 历史(见 tests/README.md)
setup.bat    一键装环境
run.bat      启动 (或双击桌面启动器)
```

## 路线图（变现/拓展）

- [ ] 多指令连说（"弓箭手散开放箭"一次出两条）
- [ ] 指令组合宏 / 一键阵型预设
- [ ] AI 意图兜底（词典没命中时交给大模型）
- [ ] 配置面板 GUI（不用手改 YAML）
- [ ] 多游戏 profile 切换，做成通用语音操作引擎
