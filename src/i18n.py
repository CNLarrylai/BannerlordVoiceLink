# -*- coding: utf-8 -*-
"""UI 双语文案 —— 语言跟随 settings.yaml 的 stt.language (zh/en)。

用法: from i18n import t
    t("👂 监听中…")  ->  en 模式返回 "👂 Listening…", zh 模式返回原文

设计取舍:
- 中文原文直接当 key: 代码里读得懂; 某条漏翻时自动退回中文, 永不崩。
- 带参数的用 {} 模板, 调用处 .format()。
- 各功能是独立进程、启动时读一次语言即可; 启动器自己切语言时调 set_lang()
  后重建界面。
"""
import yaml

from paths import config_path


def read_lang():
    try:
        with open(config_path("settings.yaml"), encoding="utf-8") as f:
            return (yaml.safe_load(f).get("stt") or {}).get("language", "zh")
    except Exception:
        return "zh"


LANG = read_lang()


def set_lang(code):
    global LANG
    LANG = code


def t(s):
    if LANG == "en":
        return _EN.get(s, s)
    return s


def text_units(s):
    """估算 Tk 字符宽度单位: 拉丁字符≈1, CJK≈2。多行取最宽一行。

    Tk 的 width= 以"平均字符宽"计, 中英文混排时用这个算出的单位数
    设置宽度, 两种语言都不会截断 (i18n 原则: 不写死字符宽)。
    """
    return max((sum(2 if ord(c) > 0x2E80 else 1 for c in line)
                for line in s.split("\n")), default=0)


_EN = {
    # ---------- 通用 ----------
    "骑砍语音指挥": "Bannerlord Voice Command",
    "关闭": "Close",
    "系统默认": "System default",
    "保存失败: {e}": "Save failed: {e}",

    # ---------- 启动器 launcher ----------
    "⚔ 骑砍语音指挥": "⚔ Bannerlord Voice Command",
    "中文语音指挥你的军队": "Command your army with your voice",
    "语言 / Language:": "语言 / Language:",
    "▶  开始语音指挥": "▶  Start Voice Command",
    "■  语音指挥运行中": "■  Voice Command running",
    "进游戏用这个：识别到指令就发按键 (需管理员)":
        "Use this in game: sends keys when a command is heard (needs admin)",
    "🎧\n测试模式": "🎧\nTest Mode",
    "只听不发键\n安全调试": "Listen only,\nno keys sent",
    "🎙\n音频设置": "🎙\nAudio Setup",
    "选麦克风\n看音量条": "Pick your mic,\nsee levels",
    "📖\n指令词典": "📖\nCommands",
    "看/加说法\n改键位": "View/add phrases,\nedit keybinds",
    "🧪\n跑测试": "🧪\nRun Tests",
    "命中率+延迟\n改完就验证": "Accuracy + latency,\nverify changes",
    "📋 查看日志": "📋 View Log",
    "📁 打开日志文件夹": "📁 Open Log Folder",
    "出问题？点「查看日志」，或发日志给作者排查":
        "Problems? Click View Log, or send the log to the author",
    "语音指挥已在运行 (看那个黑窗口)":
        "Voice Command is already running (check the console window)",
    "✓ 语音指挥已启动 (黑窗口在加载模型…)":
        "✓ Voice Command started (model loading in the console window…)",
    "✓ 测试模式已启动 (只听不发键)": "✓ Test Mode started (listen only)",
    "✓ 已打开音频设置": "✓ Audio Setup opened",
    "✓ 已打开指令词典": "✓ Command Dictionary opened",
    "✓ 已打开日志 (出问题可把它发给作者)":
        "✓ Log opened (send it to the author if something is wrong)",
    "日志还是空的 —— 先运行一次语音指挥再看":
        "Log is still empty — run Voice Command once first",
    "✓ 已打开日志文件夹 (把 app.log 发给作者即可)":
        "✓ Log folder opened (just send app.log to the author)",
    "测试仅在源码环境可用": "Tests are only available when running from source",
    "✓ 测试已启动 (黑窗里看命中率+延迟)":
        "✓ Tests started (accuracy + latency in the console)",
    "切换失败: {e}": "Switch failed: {e}",
    "✓ 已切到 {name} · 重启语音指挥生效 (Restart to apply)":
        "✓ Switched to {name} · restart Voice Command to apply",

    # ---------- 浮层 overlay ----------
    "待命中…": "Standing by…",
    "按住热键说话": "Hold the hotkey and speak",
    "上一条: (还没有)": "Last: (nothing yet)",

    # ---------- 语音主程序 main (浮层+黑窗高频行) ----------
    "👂 监听中…": "👂 Listening…",
    "说出指令即可": "just say a command",
    "按住 [{k}] 说话": "hold [{k}] to speak",
    "识别中…": "Recognizing…",
    "未匹配": "No match",
    "听到: {t}": "Heard: {t}",
    "(没听到声音)": "(no voice detected)",
    "(没听清)": "(couldn't hear that)",
    "🔄 词典已重载": "🔄 Dictionary reloaded",
    "{n} 条说法已生效": "{n} phrases active",
    "⚠ 词典重载失败": "⚠ Dictionary reload failed",
    "上一条 ✗ 没听清（识别 {s}s）": "Last ✗ couldn't hear ({s}s)",
    "上一条 · 听到「{t}」→ 无口令前缀, 忽略":
        "Last · heard \"{t}\" → no wake word, ignored",
    "上一条 ✗ 听到「{t}」→ 未匹配/聊天, 未执行":
        "Last ✗ heard \"{t}\" → no match / chat, not executed",
    "上一条 ⏸ 回声抑制「{t}」": "Last ⏸ echo suppressed \"{t}\"",
    "上一条 ✓ 听到「{t}」→ {d} · {how}（{s}s）":
        "Last ✓ heard \"{t}\" → {d} · {how} ({s}s)",
    "发键 {keys}": "keys {keys}",
    "模组直达": "via mod",
    "[目标(需准星锁定)]": "[target (aim at them!)]",
    "[模组已锁定✓]": "[locked by mod ✓]",

    # ---------- 测试模式 listen ----------
    "测试模式 · 只听不发键 — 骑砍语音指挥":
        "Test Mode · listen only — Bannerlord Voice Command",
    "🎧 测试模式（只听不发键）": "🎧 Test Mode (listen only, no keys sent)",
    "对着麦克风说指令，下面实时显示识别结果。不会往游戏发按键，随便练。":
        "Speak commands into your mic; results show below in real time. "
        "No keys are sent to the game — practice freely.",
    "启动中…": "Starting…",
    "首次下载模型 {m}（{size}）…": "First-time model download {m} ({size})…",
    "模型下载失败: {e}": "Model download failed: {e}",
    "加载识别模型中…": "Loading speech model…",
    "模型加载失败: {e}": "Model load failed: {e}",
    "👂 监听中…（说指令试试）": "👂 Listening… (try a command)",
    "已开口令前缀 {p}，要先说前缀。":
        "Wake-word prefix {p} is on — say the prefix first.",
    "⬇ 下载模型中… {pct}%  ({d}/{t} MB)": "⬇ Downloading model… {pct}%  ({d}/{t} MB)",
    "⬇ 下载模型中… 已下 {d} MB": "⬇ Downloading model… {d} MB so far",
    "未匹配 / 聊天，忽略": "no match / chat, ignored",
    "（无口令前缀，忽略）": "(no wake word, ignored)",
    "→ 按键 {keys}": "→ keys {keys}",
    "听到:「{t}」  识别{s}s": "heard: \"{t}\"  recognized in {s}s",
    "麦克风/识别出错: {e}": "Microphone / recognition error: {e}",

    # ---------- 音频设置 audio_setup ----------
    "音频与识别设置 — 骑砍语音指挥": "Audio & Recognition — Bannerlord Voice Command",
    "⚙ 音频与识别设置": "⚙ Audio & Recognition Settings",
    "🧠 识别引擎": "🧠 Recognition Engine",
    "✓ 检测到 NVIDIA 显卡, CUDA 可用 (可用 GPU 加速)":
        "✓ NVIDIA GPU detected, CUDA available (GPU acceleration ready)",
    "检测到显卡但缺 CUDA 运行库 → 本版本只能用 CPU":
        "GPU found but CUDA runtime missing → CPU only in this build",
    "未检测到可用 GPU → 用 CPU 运行": "No usable GPU detected → running on CPU",
    "模型:": "Model:",
    "运行:": "Run on:",
    "自动": "Auto",
    "跟随硬件自动选 (推荐)": "auto-pick by hardware (recommended)",
    "最快 · 准度偏低": "fastest · lower accuracy",
    "快 · 够用 (推荐)": "fast · good enough (recommended)",
    "更准 · 稍慢": "more accurate · a bit slower",
    "很准 · 明显慢": "very accurate · noticeably slower",
    "≈最准 · 较快 (推荐给N卡)": "≈best · fast (NVIDIA)",
    "最准 · 最慢": "most accurate · slowest",
    "自动 (推荐)": "Auto (recommended)",
    "强制 GPU": "Force GPU",
    "强制 CPU": "Force CPU",
    "内置": "bundled",
    "已下载": "downloaded",
    "需联网下载": "needs download",
    "⬇ 下载所选模型": "⬇ Download selected model",
    "✓ {m} 已就绪（本地已有，直接用）": "✓ {m} ready (already on this machine)",
    "⚠ {m} 未下载（{size}）—— 点右边下载":
        "⚠ {m} not downloaded ({size}) — click Download",
    "正在下载 {m} …": "Downloading {m} …",
    "下载中… {pct}%  ({d} / {t} MB)": "Downloading… {pct}%  ({d} / {t} MB)",
    "下载中… 已下 {d} MB": "Downloading… {d} MB so far",
    "✓ {m} 下载完成，已就绪": "✓ {m} downloaded and ready",
    "下载失败: {e}": "Download failed: {e}",
    "改了模型 / 运行方式后，重启语音指挥生效。":
        "After changing model / run mode, restart Voice Command to apply.",
    "🎙 麦克风：对着说话，看哪根音量条在跳，选中它，点保存":
        "🎙 Microphone: speak and watch which level bar moves, select it, Save",
    "绿色条 = 有声音进来。选中后建议再说几句确认就是这一路。":
        "Green bar = sound coming in. After selecting, say a few more words to confirm.",
    "系统默认设备": "System default device",
    "💾 保存并使用这一路": "💾 Save & use this device",
    "先选一个麦克风设备再保存": "Pick a microphone first",
    "✓ 已保存 · 麦克风:{mic} · 模型:{m} · 运行:{d}   (重启语音指挥后生效)":
        "✓ Saved · mic: {mic} · model: {m} · run: {d}   (restart Voice Command to apply)",
    "约 {n} MB": "≈ {n} MB",
    "约 {n} GB": "≈ {n} GB",
    "大小未知": "size unknown",

    # ---------- 指令词典 command_gui ----------
    "指令词典 [{mode}] — 骑砍语音指挥": "Command Dictionary [{mode}] — Bannerlord Voice",
    "中文模式": "Chinese mode",
    "英文模式 English": "English mode",
    "🇨🇳 中文说法": "🇨🇳 Chinese phrases",
    "🇬🇧 英文说法 English": "🇬🇧 English phrases",
    "📖 指令词典 · 当前显示 {mode}": "📖 Command Dictionary · showing {mode}",
    "指令": "Command",
    "按键": "Keys",
    "可以说的话 (别名)": "What you can say (aliases)",
    "🛡 兵种 (编队)": "🛡 Troops (formations)",
    "⚔ 指令 (动作)": "⚔ Orders (actions)",
    "按 {k}": "press {k}",
    "👆 选中一条, 这里显示它的全部说法":
        "👆 Select an entry to see all its phrases here",
    "✏ 改键位 (先在上面选一条):": "✏ Edit keybind (select an entry above first):",
    "未选中": "nothing selected",
    "保存键位": "Save keys",
    "格式: 空格分隔按键序列, 如「f1 f3」; 兵种填一个键如「2」。必须与游戏指令菜单一致。":
        "Format: space-separated keys, e.g. \"f1 f3\"; troops take one key like \"2\". "
        "Must match the in-game order menu.",
    "📄 打开指令树文档 (键位事实来源)": "📄 Open order-tree doc (source of truth)",
    "🧪 试一句 (看这句话会不会被执行、为什么)":
        "🧪 Try a phrase (see if it would execute, and why)",
    "测试": "Test",
    "➕ 给指令加一种新说法 (立即写入词典)":
        "➕ Add a new phrase for a command",
    "添加": "Add",
    "提示: 聊天过滤词和填充词见控制台输出":
        "Tip: chat-filter and filler word lists are printed to the console",
    "兵种: {name}": "Troop: {name}",
    "指令: {name}": "Order: {name}",
    "【{kind} · {name}】 键位 {keys}\n{say}：{phrases}":
        "[{kind} · {name}]  keys {keys}\n{say}: {phrases}",
    "兵种": "Troop",
    "能说的话": "Can say",
    "(无说法)": "(no phrases)",
    "输入: 「{t}」": "Input: \"{t}\"",
    "✗ 忽略 — {r}": "✗ Ignored — {r}",
    "  (想让它当指令? 这句话含聊天特征词, 换个说法或去掉该词)":
        "  (Want it executed? It contains a chat-marker word — rephrase it)",
    "{mark} 兵种: {name}  命中「{alias}」 {score}分":
        "{mark} Troop: {name}  matched \"{alias}\" score {score}",
    "— 没匹配到兵种 (会作用于当前选中编队)":
        "— No troop matched (order applies to currently selected formation)",
    "{mark} 指令: {name}  命中「{alias}」 {score}分":
        "{mark} Order: {name}  matched \"{alias}\" score {score}",
    "✗ 没匹配到任何指令动作": "✗ No order action matched",
    "◎ 打击目标: {name}  命中「{alias}」 {score}分  (敌方编队, 游戏内需准星锁定它)":
        "◎ Attack target: {name}  matched \"{alias}\" score {score}  "
        "(enemy formation; aim at it in game, or the mod locks it)",
    "聊天过滤: {why}": "Chat filter: {why}",
    "▶ 会执行!  发送按键: {keys}": "▶ Will execute!  keys sent: {keys}",
    "✗ 不会执行 — {r}": "✗ Will NOT execute — {r}",
    "  (应该被执行? 用下面「加说法」把关键词加进对应指令)":
        "  (Should it execute? Add the phrase to the command below)",
    "先选目标指令、再填新说法": "Pick a target command, then type the new phrase",
    "「{alias}」已存在于 {name}": "\"{alias}\" already exists under {name}",
    "写入失败: commands.yaml 里没找到该条目":
        "Write failed: entry not found in commands.yaml",
    "✓ 已把「{alias}」加进 {label} (切回语音程序按 F10 热重载生效)":
        "✓ Added \"{alias}\" to {label} (press F10 in the voice app to hot-reload)",
    "先在左侧选中一条指令再改键位": "Select an entry on the left first",
    "🌲 游戏指令树 (查验/更正键位含义)": "🌲 Game order tree (verify / correct keys)",

    # ---------- 游戏指令树 order_tree ----------
    "🌲 游戏指令树 — 查验与更正": "🌲 Game Order Tree — verify & correct",
    "🌲 游戏指令树：游戏里每个键的含义（词典键位以此校验）":
        "🌲 Game order tree: what each key does in game",
    "游戏改版/改过游戏键位时: 对照游戏内指令面板在这里更正, 再点「校验词典」。":
        "If a game patch or your keybinds change things: correct entries here "
        "against the in-game order panel, then click Validate.",
    "按键": "Key",
    "游戏内含义": "In-game meaning",
    "编队选择键": "Formation select keys",
    "顶层直接键 (无子菜单)": "Top-level direct keys (no submenu)",
    "菜单": "menu",
    "键:": "Key:",
    "含义(中/英):": "Meaning (zh / en):",
    "💾 保存修改": "💾 Save change",
    "➕ 添加子项": "➕ Add entry",
    "🗑 删除所选": "🗑 Delete selected",
    "🔍 校验词典": "🔍 Validate dictionary",
    "👆 选中一行可编辑; 改完即写入配置": "👆 Select a row to edit; saves to config",
    "先在上面选中一行": "Select a row above first",
    "这一行是分组标题, 不能编辑": "That row is a section header, not editable",
    "键必须是 f1~f9 或数字 0~9": "Key must be f1~f9 or a digit 0~9",
    "键 {k} 已存在": "Key {k} already exists",
    "✓ 已保存到 order_tree.yaml": "✓ Saved to order_tree.yaml",
    "先在「键」里填新按键 (f1~f9 或 0~9)": "Type the new key first (f1~f9 or 0~9)",
    "✓ 已添加并保存": "✓ Added and saved",
    "✓ 已删除并保存": "✓ Deleted and saved",
    "整个菜单/分组不允许删 (删它下面的具体键)":
        "Menus / sections can't be deleted (delete their child keys)",
    "校验结果 — 词典键位 vs 指令树": "Validation — dictionary keys vs order tree",
    "❌ {n} 条键位走不通指令树, 请修正:":
        "❌ {n} key sequences don't resolve in the order tree, please fix:",
    "✓ 词典全部 {n} 条键位都能在指令树里走通":
        "✓ All {n} dictionary key sequences resolve in the order tree",
    "空键序": "empty key sequence",
    "{k} 只是打开菜单, 后面缺选项键": "{k} only opens a menu, missing the item key",
    "{k} 不在指令树里 (既非直接键也非菜单)":
        "{k} is not in the order tree (neither direct key nor menu)",
    "{k} 不是菜单键, 不能接子选项": "{k} is not a menu key, can't take sub-items",
    "{menu} 菜单里没有 {k}": "menu {menu} has no {k}",
    "{k} 不在编队选择键里": "{k} is not a formation select key",
    "键位不能为空": "Keys cannot be empty",
    "无效按键: {bad} (如 f1 f3 或 0~9)": "Invalid keys: {bad} (e.g. f1 f3 or 0~9)",
    "兵种只填一个选中键 (如 2)": "Troops take exactly one select key (e.g. 2)",
    "✓ 「{name}」键位已改为 {keys} (切回语音程序按 F10 热重载生效)":
        "✓ \"{name}\" keybind changed to {keys} (press F10 to hot-reload)",
    "指令树文档仅源码版附带": "The order-tree doc ships with the source version only",
}
