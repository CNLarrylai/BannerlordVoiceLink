"""启动器 Hub —— 一个入口, 汇总全部功能。

双击桌面图标打开这个面板, 四个按钮:
  ▶ 开始语音指挥   (正式版: 识别 -> 发按键, 进游戏用)
  🎧 测试模式      (只听不发键, 安全调试)
  🎙 音频设置      (选麦克风)
  📖 指令词典      (看/加说法、改键位)

语音引擎和测试模式各自开一个黑窗(看日志); 两个设置窗口是 GUI。
"""
import os
import subprocess
import sys
import tkinter as tk

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import i18n  # noqa: E402
from i18n import t  # noqa: E402
ROOT = os.path.dirname(_HERE)
FROZEN = getattr(sys, "frozen", False)
SCRIPTS = os.path.dirname(sys.executable)
PY = os.path.join(SCRIPTS, "python.exe")
PYW = os.path.join(SCRIPTS, "pythonw.exe")
if not os.path.exists(PYW):
    PYW = PY

CREATE_NEW_CONSOLE = 0x00000010

BG = "#101418"
FG = "#e8edf2"
DIM = "#9aa4ad"
GOLD = "#d4af37"
GREEN = "#7dff9b"
GRAY = "#2a323a"


def _read_language():
    try:
        import yaml
        from paths import config_path
        with open(config_path("settings.yaml"), encoding="utf-8") as f:
            return (yaml.safe_load(f).get("stt") or {}).get("language", "zh")
    except Exception:
        return "zh"


def _write_language(lang):
    import re
    from paths import config_path
    p = config_path("settings.yaml")
    with open(p, encoding="utf-8") as f:
        lines = f.readlines()
    in_stt = False
    for i, line in enumerate(lines):
        if re.match(r"^\S", line):
            in_stt = line.startswith("stt:")
        if in_stt and re.match(r"^\s+language\s*:", line):
            lines[i] = f"  language: {lang}\n"
            break
    with open(p, "w", encoding="utf-8") as f:
        f.writelines(lines)


def _spawn(mode, console):
    """按 mode 拉起一个功能子进程。源码/打包两种形态都成立。

    console=True 的功能(语音/测试)要有黑窗看日志; GUI 无窗。
    """
    if FROZEN:
        # 打包后: exe 用 --mode 再拉起自己。全部 windowed(无黑窗), 日志写文件,
        # 界面反馈靠浮层 —— 成品体验更干净。
        argv = [sys.executable, "--mode", mode]
        flags = 0
    else:
        # 源码: console 模式用 python.exe(自带黑窗), GUI 用 pythonw.exe(无窗)
        exe = PY if console else PYW
        argv = [exe, os.path.join(ROOT, "src", "app.py"), "--mode", mode]
        flags = 0
    return subprocess.Popen(argv, cwd=ROOT, creationflags=flags)


class Launcher:
    def __init__(self):
        self.voice_proc = None
        self.lang = _read_language()
        i18n.set_lang(self.lang)
        self.root = tk.Tk()
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        self._build_ui()
        self.root.after(1000, self._poll_voice)

    def _build_ui(self):
        """整体构建界面 (切语言时清空重建, 所有文案立即换语言)。"""
        for w in self.root.winfo_children():
            w.destroy()
        self.root.title(t("骑砍语音指挥"))

        tk.Label(self.root, text=t("⚔ 骑砍语音指挥"), fg=GOLD, bg=BG,
                 font=("Microsoft YaHei", 20, "bold")).pack(padx=40, pady=(22, 2))
        tk.Label(self.root, text=t("中文语音指挥你的军队"), fg=DIM, bg=BG,
                 font=("Microsoft YaHei", 11)).pack(pady=(0, 10))

        # 语言切换 (中文 / English)
        langrow = tk.Frame(self.root, bg=BG)
        langrow.pack(pady=(0, 14))
        tk.Label(langrow, text="语言 / Language:", fg=DIM, bg=BG,
                 font=("Microsoft YaHei", 10)).pack(side="left", padx=(0, 8))
        self.zh_btn = tk.Button(langrow, text="中文", relief="flat", padx=16, pady=3,
                                font=("Microsoft YaHei", 10, "bold"),
                                command=lambda: self._set_lang("zh"))
        self.zh_btn.pack(side="left", padx=3)
        self.en_btn = tk.Button(langrow, text="English", relief="flat", padx=16, pady=3,
                                font=("Microsoft YaHei", 10, "bold"),
                                command=lambda: self._set_lang("en"))
        self.en_btn.pack(side="left", padx=3)
        self._refresh_lang_btns()

        # 主按钮: 开始语音指挥
        self.start_btn = tk.Button(
            self.root, text=t("▶  开始语音指挥"), command=self.start_voice,
            font=("Microsoft YaHei", 16, "bold"), bg=GOLD, fg="#101418",
            activebackground="#e8c95a", relief="flat", padx=20, pady=12, width=20,
        )
        self.start_btn.pack(padx=40, pady=(0, 4))
        tk.Label(self.root, text=t("进游戏用这个：识别到指令就发按键 (需管理员)"),
                 fg=DIM, bg=BG, font=("Microsoft YaHei", 9)).pack(pady=(0, 16))

        # 次要按钮 (宽度按当前语言的最长文案计算, 防止英文被截断)
        row = tk.Frame(self.root, bg=BG)
        row.pack(padx=30, pady=(0, 6))
        minis = [
            (t("🎯\n上手校准"), t("跟读学指令\n适配你的发音"), self.start_calibrate),
            (t("🎧\n测试模式"), t("只听不发键\n安全调试"), self.start_listen),
            (t("🎙\n音频设置"), t("选麦克风\n看音量条"), self.open_audio),
            (t("📖\n指令词典"), t("看/加说法\n改键位"), self.open_dict),
            (t("🧪\n跑测试"), t("命中率+延迟\n改完就验证"), self.run_tests),
        ]
        btn_w = max(i18n.text_units(title) for title, _, _ in minis) + 2
        for title, sub, cmd in minis:
            self._mini(row, title, sub, cmd, btn_w)

        # 底部: 查看日志 (自己排错 / 发给作者)
        foot = tk.Frame(self.root, bg=BG)
        foot.pack(pady=(14, 4))
        tk.Button(foot, text=t("📋 查看日志"), command=self.open_log,
                  font=("Microsoft YaHei", 10), bg="#2a323a", fg=FG,
                  activebackground="#3a444e", relief="flat", padx=12, pady=3).pack(
            side="left", padx=5)
        tk.Button(foot, text=t("📁 打开日志文件夹"), command=self.open_log_folder,
                  font=("Microsoft YaHei", 10), bg="#2a323a", fg=FG,
                  activebackground="#3a444e", relief="flat", padx=12, pady=3).pack(
            side="left", padx=5)

        self.status = tk.Label(self.root,
                               text=t("出问题？点「查看日志」，或发日志给作者排查"),
                               fg=DIM, bg=BG, font=("Microsoft YaHei", 9))
        self.status.pack(pady=(6, 16))
        self._refresh_start_btn()

    def _mini(self, parent, title, sub, cmd, width):
        f = tk.Frame(parent, bg=BG)
        f.pack(side="left", padx=5)
        tk.Button(f, text=title, command=cmd, font=("Microsoft YaHei", 12, "bold"),
                  bg=GRAY, fg=FG, activebackground="#3a444e", relief="flat",
                  width=width, height=2).pack()
        tk.Label(f, text=sub, fg=DIM, bg=BG, font=("Microsoft YaHei", 8),
                 justify="center").pack(pady=(4, 0))

    def _set(self, text, color=GREEN):
        self.status.config(text=text, fg=color)

    def _refresh_lang_btns(self):
        for btn, code in ((self.zh_btn, "zh"), (self.en_btn, "en")):
            if code == self.lang:
                btn.config(bg=GOLD, fg="#101418", activebackground="#e8c95a")
            else:
                btn.config(bg=GRAY, fg=FG, activebackground="#3a444e")

    def _set_lang(self, lang):
        if lang == self.lang:
            return
        try:
            _write_language(lang)
        except Exception as e:
            self._set(t("切换失败: {e}").format(e=e), "#ff8a8a")
            return
        self.lang = lang
        i18n.set_lang(lang)
        self._build_ui()   # 整个界面立即换语言
        name = "中文" if lang == "zh" else "English"
        self._set(t("✓ 已切到 {name} · 重启语音指挥生效 (Restart to apply)")
                  .format(name=name), GOLD)

    def start_voice(self):
        if self.voice_proc and self.voice_proc.poll() is None:
            self._set(t("语音指挥已在运行 (看那个黑窗口)"), GOLD)
            return
        self.voice_proc = _spawn("voice", console=True)
        self._set(t("✓ 语音指挥已启动 (黑窗口在加载模型…)"))
        self._refresh_start_btn()

    def start_calibrate(self):
        _spawn("calibrate", console=False)
        self._set(t("✓ 上手校准已启动 (跟着屏幕念)"))

    def start_listen(self):
        _spawn("listen", console=False)
        self._set(t("✓ 测试模式已启动 (只听不发键)"))

    def open_audio(self):
        _spawn("audio", console=False)
        self._set(t("✓ 已打开音频设置"))

    def open_dict(self):
        _spawn("dict", console=False)
        self._set(t("✓ 已打开指令词典"))

    def open_log(self):
        from paths import log_file
        p = log_file()
        if os.path.exists(p) and os.path.getsize(p) > 0:
            os.startfile(p)
            self._set(t("✓ 已打开日志 (出问题可把它发给作者)"))
        else:
            self._set(t("日志还是空的 —— 先运行一次语音指挥再看"), GOLD)

    def open_log_folder(self):
        from paths import log_dir
        os.startfile(log_dir())
        self._set(t("✓ 已打开日志文件夹 (把 app.log 发给作者即可)"))

    def run_tests(self):
        # 测试是开发向工具, 打包版里不带; 源码下才拉起
        if FROZEN:
            self._set(t("测试仅在源码环境可用"), GOLD)
            return
        exe = PY
        argv = [exe, os.path.join(ROOT, "tests", "run_all.py")]
        subprocess.Popen(argv, cwd=ROOT)
        self._set(t("✓ 测试已启动 (黑窗里看命中率+延迟)"))

    def _refresh_start_btn(self):
        running = self.voice_proc and self.voice_proc.poll() is None
        if running:
            self.start_btn.config(text=t("■  语音指挥运行中"), bg=GREEN)
        else:
            self.start_btn.config(text=t("▶  开始语音指挥"), bg=GOLD)

    def _poll_voice(self):
        self._refresh_start_btn()
        self.root.after(1000, self._poll_voice)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    Launcher().run()
