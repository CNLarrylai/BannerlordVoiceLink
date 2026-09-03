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
    # ---------- 首次 GPU 加速引导 gpu_setup ----------
    "发现你的显卡可以加速": "Your GPU can speed this up",
    "🚀 检测到 NVIDIA 显卡": "🚀 NVIDIA GPU detected",
    ("你的显卡可以让语音识别又快又准, 但还缺一个 GPU 加速库\n"
     "({size}, 一次性下载)。\n\n"
     "下载后: 识别更准, 疑难指令的兜底速度从约 1.7 秒降到 0.2 秒。\n"
     "不下载也完全能用 —— 现在走 CPU 档, 一样能指挥。"):
        ("Your GPU can make recognition faster and more accurate, but the GPU\n"
         "acceleration library is missing ({size}, one-time download).\n\n"
         "After installing: better accuracy, and the fallback for tricky commands\n"
         "drops from ~1.7s to ~0.2s. It works fine without it too (CPU mode)."),
    "⬇ 下载并启用 GPU 加速": "⬇ Download & enable GPU acceleration",
    "以后再说": "Maybe later",
    "正在下载… 可以先去玩, 下完会提示":
        "Downloading… feel free to play; you'll be notified when it's done",
    "下载中 {pct}%  ({d} / {t} MB)": "Downloading {pct}%  ({d} / {t} MB)",
    "✓ 已启用 GPU 加速, 识别模型已切到最强档":
        "✓ GPU acceleration enabled — switched to the best model",
    "✓ 下载完成 (模型档位请在音频设置里选)":
        "✓ Download complete (pick the model in Audio Setup)",
    "下载失败: {e} (可稍后在音频设置里重试)":
        "Download failed: {e} (retry later in Audio Setup)",
    "完成": "Done",
    "检测到可用显卡 —— 见弹窗": "GPU detected — see the dialog",

    "📋 查看日志": "📋 View Log",
    "📦 打包日志 (报障用)": "📦 Pack Logs (for bug reports)",
    "打包日志": "Pack logs",
    "日志": "logs",
    "_版本": "_version",
    "还没有日志 (先运行一次语音指挥)":
        "No logs yet — run Voice Command once first",
    ("日志已打包(不含任何录音):\n{p}\n\n"
     "文件夹已打开并高亮它 —— 把这个文件发给作者即可。"):
        ("Logs packed (no audio included):\n{p}\n\n"
         "The folder is open with the file highlighted — just send it to the author."),
    "✓ 日志已打包, 把高亮的文件发给作者":
        "✓ Logs packed — send the highlighted file to the author",
    "出问题？点「打包日志」，把生成的文件发给作者":
        "Problems? Click Pack Logs and send the file to the author",
    "🛑 全部停止": "🛑 Stop All",
    "🛑 已停止 {n} 个语音进程": "🛑 Stopped {n} voice process(es)",
    "没有其它语音进程在跑 (已是干净状态)": "No other voice processes running (clean)",
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
    "切换失败: {e}": "Switch failed: {e}",
    "✓ 已切到 {name} · 重启语音指挥生效 (Restart to apply)":
        "✓ Switched to {name} · restart Voice Command to apply",

    "🎯\n上手校准": "🎯\nCalibrate",
    "跟读学指令\n适配你的发音": "Learn commands,\ntune to your voice",
    "✓ 上手校准已启动 (跟着屏幕念)": "✓ Calibration started (read the prompts)",

    # ---------- 语音数据共建 donation ----------
    "🎤 参与语音数据共建 (自愿, 只存指令片段)":
        "🎤 Donate voice data (optional, command clips only)",
    "📦 导出数据包": "📦 Export data pack",
    "语音数据共建": "Voice Data Donation",
    "✓ 已开启共建 (语音指挥运行中的话按 F10 生效)":
        "✓ Donation on (press F10 in the voice app to apply)",
    "已关闭共建, 不再保存任何片段": "Donation off — no clips will be saved",
    "还没有留存的片段 (先勾选共建并打几场)":
        "No clips saved yet (enable donation and play some battles)",
    "导出失败: {e}": "Export failed: {e}",
    "✓ 数据包已导出 ({n}条/{mb}MB), 把它发给作者即可":
        "✓ Data pack exported ({n} clips / {mb}MB) — send it to the author",
    "上传数据包": "Upload data pack",
    ("数据包已生成并在文件夹里高亮:\n{p}\n\n上传页已在浏览器打开 —— "
     "把那个高亮的文件拖进网页即可 (不用登录)。\n\n"
     "共 {n} 条 / {mb}MB。谢谢参与!"):
        ("Your data pack is ready and highlighted in the folder:\n{p}\n\n"
         "The upload page just opened in your browser — drag that highlighted "
         "file into the page (no login needed).\n\n"
         "{n} clips / {mb}MB. Thank you!"),
    "✓ 已导出并打开上传页, 把高亮文件拖进去即可":
        "✓ Exported & upload page opened — drag the highlighted file in",
    ("参与「语音数据共建」意味着:\n\n"
     "· 只保存「被识别为指令并执行」的那 1~2 秒语音片段和识别文本\n"
     "  (聊天、闲话、未匹配的内容一律不保存)\n"
     "· 数据只存在你自己电脑上 (%LOCALAPPDATA%\\BannerlordVoice\\donation)\n"
     "· 只有你自己点「导出数据包」并把它发给作者, 数据才会离开你的电脑\n"
     "· 数据包只含语音片段、指令标注、软件版本和一个匿名机器编号,\n"
     "  不含你的任何个人信息\n"
     "· 用途: 训练/微调更小更快的指令识别模型, 让所有玩家受益\n"
     "· 随时可以取消勾选停止保存; 删掉那个文件夹即可清空\n\n"
     "确认参与吗?"):
        ("Joining Voice Data Donation means:\n\n"
         "- Only the 1-2s clips of RECOGNIZED AND EXECUTED commands (plus the\n"
         "  recognized text) are saved. Chat and unmatched speech are never saved.\n"
         "- Data stays on YOUR computer\n"
         "  (%LOCALAPPDATA%\\BannerlordVoice\\donation)\n"
         "- Data only leaves your machine when YOU click Export and send the\n"
         "  pack to the author\n"
         "- The pack contains only: audio clips, command labels, app version,\n"
         "  and an anonymous machine hash. No personal information.\n"
         "- Purpose: fine-tune a smaller, faster command model for everyone\n"
         "- Untick anytime to stop; delete the folder to wipe everything\n\n"
         "Join?"),

    # ---------- 指令复盘 review ----------
    "📜\n指令复盘": "📜\nReview",
    "看识别记录\n纠错改绑定": "Browse history,\nfix bindings",
    "✓ 已打开指令复盘 (游戏里也可按 F11 呼出)":
        "✓ Command Review opened (press F11 in game too)",
    "指令复盘": "Command Review",
    "📜 指令复盘 — 每句话都听成了什么、触发了什么":
        "📜 Command Review — what was heard, what was triggered",
    "发现错配: 选中那条 → 指定正确指令/兵种 → 学进个人词典":
        "Found a mismatch? Select it → set the right command → learn it",
    "时间": "Time",
    "听到": "Heard",
    "判定": "Parsed",
    "方式": "Via",
    "耗时": "Sec",
    "✗ 未匹配": "✗ no match",
    "模组": "mod",
    "按键": "keys",
    "↑ 选中一条记录查看/纠错": "↑ Select a row to inspect / fix",
    "听到: 「{t}」": "Heard: \"{t}\"",
    "正确兵种:": "Correct troop:",
    "正确指令:": "Correct order:",
    "打击目标:": "Attack target:",
    "(不指定)": "(none)",
    "(无)": "(none)",
    "要学的说法(自动提取, 可改):": "Phrase to learn (auto-filled, editable):",
    "✎ 保存绑定(学进个人词典)": "✎ Learn this phrase",
    "🔄 刷新": "🔄 Refresh",
    "绑定保存后: 语音程序按 F10 生效, 下次启动自动生效":
        "After saving: press F10 in the voice app to apply (auto on restart)",
    "还没有记录: 先开语音指挥打一场": "No records yet — play a battle first",
    "把下面的兵种/指令改成这句话该触发的, 再点保存":
        "Set the troop/order this phrase SHOULD trigger, then save",
    "先在表格里选中一条记录": "Select a row in the table first",
    "没有可保存的改动 (兵种/指令都与记录相同)":
        "Nothing to save (troop/order unchanged)",
    "说法「{a}」太短(至少2个字), 请在输入框改":
        "Phrase \"{a}\" is too short (min 2 chars), edit it above",
    "✓ 已学 {d} · 语音程序按 F10 生效(重启也生效)":
        "✓ Learned {d} · press F10 in the voice app to apply",

    # ---------- 校准 calibrate ----------
    "上手校准 — 骑砍语音指挥": "Calibration — Bannerlord Voice Command",
    "🎯 上手校准（教学 + 发音适配）": "🎯 Calibration (learn commands + tune to your voice)",
    "跟着屏幕念指令, 系统实时判定。全部念完会生成报告, 并把「你的稳定错听」学进个人词典 —— 越用越懂你。":
        "Read the prompted commands aloud; each is checked live. At the end you "
        "get a report, and your consistent mis-hearings are learned into your "
        "personal dictionary — it adapts to you.",
    "点「开始」后跟着念": "Choose a run, then read aloud",
    "▶ 开始": "▶ Start",
    "▶ 开始校准 (约3分钟)": "▶ Start calibration (~3 min)",
    "▶ 完整校准 (全部指令, 约6分钟)": "▶ Full run (~6 min)",
    "快速校准 (常用指令)": "Quick run (most-used)",
    "题目来源: 完整指令库 (当前版本支持的全部指令各一遍, 共{n}条)":
        "Source: full command set (every supported command once, {n} items)",
    "跳过这条": "Skip",
    "流程一共 4 步:": "Four steps:",
    "先不学": "Not now",
    "· 本轮建议未采纳 (随时可再跑一轮)":
        "· Suggestions skipped (run another round anytime)",
    "题目来源: 你的使用记录 Top{n} (最常用优先)":
        "Drill source: your usage Top{n} (most-used first)",
    "题目来源: 默认题库 (使用数据攒够后自动改用你的常用指令)":
        "Drill source: default list (switches to your most-used commands "
        "once enough usage data exists)",
    "题目来源: 内置题库": "Drill source: built-in list",
    "  ① 点「完整校准」或「快速校准」(首次会加载识别模型, 稍等)":
        "  1. Click Full run or Quick run (the speech model loads first, one moment)",
    "  ② 屏幕大字出题, 共 {n} 条 —— 对着麦克风念出来即可; 没念对自动给第二次机会, 也可点「跳过这条」":
        "  2. Read the {n} prompted commands aloud; misses get a second try, "
        "or click Skip",
    "  ③ 全部念完自动出报告: 命中率 + 平均识别速度":
        "  3. A report appears: hit rate + average recognition speed",
    "  ④ 若发现「你的稳定错听」, 一键学进个人词典, 以后就按你的念法识别":
        "  4. Consistent mis-hearings can be learned into your personal "
        "dictionary with one click",
    "加载识别模型中…": "Loading speech model…",
    "校准出错: {e}": "Calibration error: {e}",
    "请念：「{s}」": "Say: \"{s}\"",
    "第 {i} / {n} 条": "{i} / {n}",
    "👂 听你说…": "👂 Listening…",
    "✓ 很好！({s}s)": "✓ Nice! ({s}s)",
    " · 再念一次试试": " · try once more",
    "✗ 听到「{h}」没对上{more}": "✗ heard \"{h}\", no match{more}",
    "🎉 校准完成": "🎉 Calibration complete",
    "  「{say}」→ 你的说法「{alias}」": "  \"{say}\" → you say \"{alias}\"",
    "已切到快速校准: {src}": "Switched to Quick run: {src}",
    "已切到完整校准: {src}": "Switched to Full run: {src}",
    "命中 {p}% · 平均识别 {s}s · 录音已存本地":
        "Hit rate {p}% · avg recognition {s}s · recordings saved locally",
    "—— 报告: {n} 条练习, 命中率 {p}% ——":
        "—— Report: {n} drills, hit rate {p}% ——",
    "发现你的稳定说法/错听, 建议学进个人词典:":
        "Found your consistent phrasings / mis-hearings, suggest learning them:",
    "✍ 学进我的个人词典": "✍ Learn into my dictionary",
    "▶ 再来一轮": "▶ Another round",
    "✓ 已写入 {n} 条到个人词典 (语音程序按 F10 生效)":
        "✓ {n} entries saved to personal dictionary (press F10 in the voice app)",

    # ---------- 浮层 overlay ----------
    "待命中…": "Standing by…",
    "按住热键说话": "Hold the hotkey and speak",
    "上一条: (还没有)": "Last: (nothing yet)",

    # ---------- 语音主程序 main (浮层+黑窗高频行) ----------
    "👂 监听中…": "👂 Listening…",
    "说出指令即可": "just say a command",
    "按住 [{k}] 说话": "hold [{k}] to speak",
    "识别中…": "Recognizing…",
    "🔇 已关闭识别": "🔇 Recognition off",
    "按 [{k}] 开启": "press [{k}] to enable",
    "🔇 战斗外静音": "🔇 Muted (not in battle)",
    "进入战斗自动开启": "auto-enables when battle starts",
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
    "⚙ 需要模组": "⚙ Needs the companion mod",
    "游戏没开或模组没启用": "game not running, or mod not enabled",
    "⚙ 要指定兵种或全军": "⚙ Name a troop type or 'everyone'",
    "例：骑兵绕后": "e.g. 'cavalry flank'",
    "⚙ 只支持护弓箭手": "⚙ Only the archers can be protected",
    "⚙ 护卫要说明护谁": "⚙ Say who to protect",
    "⚙ 不能护自己": "⚙ Can't protect themselves",
    "场上没有这支要护的队伍": "no such formation on the field to protect",
    "例：骑兵保护弓箭手": "e.g. 'cavalry protect the archers'",
    "⚙ 弓箭手不能护自己": "⚙ Archers can't protect themselves",
    "例：步兵保护弓箭手": "e.g. 'infantry protect the archers'",
    "⚙ 分队要指定兵种": "⚙ Split needs a troop type",
    "例：骑兵分队": "e.g. 'cavalry split'",
    "⚙ 分队未执行": "⚙ Not executed",
    "⚙ 模组未连接": "⚙ Mod not connected",
    "游戏没开或不在战斗": "game not running, or not in battle",
    "⚙ 左右队暂不支持这条": "⚙ Half-groups can't take this order",
    "仅冲锋/前进/跟随/待命/后退/撤退；定点移动用'跟我'":
        "only charge / advance / follow / halt / fall back / retreat; say 'follow me' to reposition",
    "还没分队(先喊'骑兵分队')": "not split yet (say 'cavalry split' first)",
    "这队人太少, 分不了": "too few units to split",
    "这个队现在没兵(先分队或换个队号)": "that group is empty (split first, or pick another number)",
    "队号要在 1-8 之间": "group number must be 1-8",
    "编队槽满了(最多分出4支), 新战斗才清空": "no free formation slot (max 4 splits); resets next battle",
    "不在战斗中": "not in battle",
    "(太短)": "(too short)",
    "⚠ 麦克风打开失败": "⚠ Microphone failed to open",
    "请打开「音频设置」换一路设备": "open Audio Setup and pick another device",
    "🎙 录音中…": "🎙 Recording…",
    "场上没有弓箭手可护": "no archers on the field to protect",
    "快路": "stream",
    "(无说法)": "(no phrases)",
    "语音数据包": "voice-data",
    # ---------- 音频设备错误 audio (测试模式窗口/浮层会原样显示) ----------
    "找不到输入设备「{name}」, 请打开音频输入设置重新选择。":
        "Input device \"{name}\" not found. Open Audio Setup and pick another one.",
    ("输入设备「{name}」的所有通道都无法打开。\n"
     "最可能的原因: 它被其他软件独占 (如 Voicemeeter 把它当硬件输入)。\n"
     "解决: 打开「语音指挥·音频设置」, 改选一路能跳绿条的设备 "
     "(比如 Voicemeeter Out B1 或 NVIDIA Broadcast)。\n"
     "详细尝试记录: {errors}"):
        ("Could not open any channel of input device \"{name}\".\n"
         "Most likely another app holds it exclusively (e.g. Voicemeeter using it as a hardware input).\n"
         "Fix: open Audio Setup and pick a device whose level bar moves "
         "(e.g. Voicemeeter Out B1 or NVIDIA Broadcast).\n"
         "Attempts: {errors}"),
    # ---------- CUDA 下载错误 cuda_libs (音频设置/引导弹窗状态行显示) ----------
    "{pkg} {ver} 找不到 win_amd64 wheel: {err}":
        "No win_amd64 wheel found for {pkg} {ver}: {err}",
    "所有下载源都失败了: {err}": "All download sources failed: {err}",
    "下载后仍缺: {missing}": "Still missing after download: {missing}",
    # ---------- matcher 判定说明 (词典窗口测试台显示) ----------
    "剔除填充词后仍有 {n} 个词 (> {max}), 按聊天处理":
        "{n} words left after removing fillers (> {max}), treated as chat",
    "剩余杂词仅 {n} 个, 放行": "only {n} stray word(s) left, allowed",
    "指令占比 {cov} < {min} (剩余杂词「{left}」太多), 按聊天处理":
        "command share {cov} < {min} (too many stray words: \"{left}\"), treated as chat",
    "指令占比 {cov} ≥ {min}, 放行": "command share {cov} ≥ {min}, allowed",
    "剔除填充词后仍有 {n} 字 (> {max}), 按聊天处理":
        "{n} characters left after removing fillers (> {max}), treated as chat",
    "剩余杂字仅 {n} 个, 放行": "only {n} stray character(s) left, allowed",
    "指令占比 {cov} < {min} (剩余杂字「{left}」太多), 按聊天处理":
        "command share {cov} < {min} (too many stray characters: \"{left}\"), treated as chat",
    "空文本": "empty text",
    "只有标点/空白": "only punctuation / whitespace",
    "含聊天特征词「{hit}」, 判为聊天": "contains chat marker \"{hit}\", treated as chat",
    "没有匹配到指令动作 (最接近: {key} {score}分, 阈值 {th})":
        "no order matched (closest: {key} score {score}, threshold {th})",
    "没有匹配到任何指令动作": "no order matched",
    "指令只命中单字「{alias}」, 句中还有「{left}」, 疑似错听, 不执行":
        "only the single-character alias \"{alias}\" matched and \"{left}\" remains; likely a mis-hearing, not executed",
    "执行": "execute",

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
    "检测到 N 卡但缺 CUDA 库 → 下载后即可 GPU 加速":
        "NVIDIA GPU found, CUDA libs missing → download to enable GPU",
    "未检测到可用 GPU → 用 CPU 运行": "No usable GPU detected → running on CPU",
    "⬇ 下载 GPU 加速库 ({size})": "⬇ Download GPU libs ({size})",
    "⬇ 下载 ({size})": "⬇ Download ({size})",
    "📁 已有?指定文件夹": "📁 Have it? Pick folder",
    "选择含 cuBLAS/cuDNN 的文件夹 (如 …\\nvidia)":
        "Pick a folder containing cuBLAS/cuDNN (e.g. …\\nvidia)",
    "✓ 已认到本地 CUDA 库，无需下载！运行选「自动/GPU」并重启即可":
        "✓ Found local CUDA libs, no download needed! Set Run to Auto/GPU and restart",
    "这里只找到部分 CUDA 库，缺 cuBLAS 或 cuDNN；换个更全的文件夹或直接下载":
        "Only part of the CUDA libs here (missing cuBLAS or cuDNN); pick a fuller "
        "folder or just download",
    "该文件夹(含子目录)里没找到 CUDA 库(cublas64_12.dll / cudnn64_9.dll)":
        "No CUDA libs (cublas64_12.dll / cudnn64_9.dll) found in that folder",
    "约 1.2 GB": "~1.2 GB",
    "正在下载 GPU 加速库…（约 1.2GB，一次性）":
        "Downloading GPU libraries… (~1.2 GB, one time)",
    "下载 GPU 加速库… {pct}%  ({d} / {t} MB)":
        "Downloading GPU libs… {pct}%  ({d} / {t} MB)",
    "✓ GPU 加速库已就绪！运行选「自动/GPU」并重启语音指挥即可":
        "✓ GPU libs ready! Set Run to Auto/GPU and restart Voice Command",
    "GPU 加速库下载失败: {e}": "GPU library download failed: {e}",
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
        "🎙 Microphone: speak, select the device whose bar moves, then Save",
    "绿色条 = 有声音进来。选中后建议再说几句确认就是这一路。":
        "Green bar = sound coming in. After selecting, say a few more words to confirm.",
    "系统默认设备": "System default device",
    "💾 保存并使用这一路": "💾 Save & use this device",
    "先选一个麦克风设备再保存": "Pick a microphone first",
    "✓ 已保存 · 麦克风:{mic} · 模型:{m} · 运行:{d}   (重启语音指挥后生效)":
        "✓ Saved · mic: {mic} · model: {m} · run: {d}   (restart Voice Command to apply)",
    "⚠ CPU 上跑 {m} 会很慢(每句数秒), 无独显强烈建议 base":
        "⚠ {m} on CPU is very slow (seconds per phrase); without a GPU use base",
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
    "提示: 在上面输入一句话, 看它会不会执行、为什么":
        "Tip: type a phrase above to see whether it would execute, and why",
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
    "含义(中/英):": "Meaning (中文 / English):",
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
