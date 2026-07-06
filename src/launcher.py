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
        self.root = tk.Tk()
        self.root.title("骑砍语音指挥")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)

        tk.Label(self.root, text="⚔ 骑砍语音指挥", fg=GOLD, bg=BG,
                 font=("Microsoft YaHei", 20, "bold")).pack(padx=40, pady=(22, 2))
        tk.Label(self.root, text="中文语音指挥你的军队", fg=DIM, bg=BG,
                 font=("Microsoft YaHei", 11)).pack(pady=(0, 16))

        # 主按钮: 开始语音指挥
        self.start_btn = tk.Button(
            self.root, text="▶  开始语音指挥", command=self.start_voice,
            font=("Microsoft YaHei", 16, "bold"), bg=GOLD, fg="#101418",
            activebackground="#e8c95a", relief="flat", padx=20, pady=12, width=20,
        )
        self.start_btn.pack(padx=40, pady=(0, 4))
        tk.Label(self.root, text="进游戏用这个：识别到指令就发按键 (需管理员)",
                 fg=DIM, bg=BG, font=("Microsoft YaHei", 9)).pack(pady=(0, 16))

        # 次要按钮
        row = tk.Frame(self.root, bg=BG)
        row.pack(padx=30, pady=(0, 6))
        self._mini(row, "🎧\n测试模式", "只听不发键\n安全调试", self.start_listen)
        self._mini(row, "🎙\n音频设置", "选麦克风\n看音量条", self.open_audio)
        self._mini(row, "📖\n指令词典", "看/加说法\n改键位", self.open_dict)
        self._mini(row, "🧪\n跑测试", "命中率+延迟\n改完就验证", self.run_tests)

        # 底部: 查看日志 (自己排错 / 发给作者)
        foot = tk.Frame(self.root, bg=BG)
        foot.pack(pady=(14, 4))
        tk.Button(foot, text="📋 查看日志", command=self.open_log,
                  font=("Microsoft YaHei", 10), bg="#2a323a", fg=FG,
                  activebackground="#3a444e", relief="flat", padx=12, pady=3).pack(
            side="left", padx=5)
        tk.Button(foot, text="📁 打开日志文件夹", command=self.open_log_folder,
                  font=("Microsoft YaHei", 10), bg="#2a323a", fg=FG,
                  activebackground="#3a444e", relief="flat", padx=12, pady=3).pack(
            side="left", padx=5)

        self.status = tk.Label(self.root, text="出问题？点「查看日志」，或发日志给作者排查",
                               fg=DIM, bg=BG, font=("Microsoft YaHei", 9))
        self.status.pack(pady=(6, 16))

        self.root.after(1000, self._poll_voice)

    def _mini(self, parent, title, sub, cmd):
        f = tk.Frame(parent, bg=BG)
        f.pack(side="left", padx=5)
        tk.Button(f, text=title, command=cmd, font=("Microsoft YaHei", 12, "bold"),
                  bg=GRAY, fg=FG, activebackground="#3a444e", relief="flat",
                  width=7, height=2).pack()
        tk.Label(f, text=sub, fg=DIM, bg=BG, font=("Microsoft YaHei", 8),
                 justify="center").pack(pady=(4, 0))

    def _set(self, text, color=GREEN):
        self.status.config(text=text, fg=color)

    def start_voice(self):
        if self.voice_proc and self.voice_proc.poll() is None:
            self._set("语音指挥已在运行 (看那个黑窗口)", GOLD)
            return
        self.voice_proc = _spawn("voice", console=True)
        self._set("✓ 语音指挥已启动 (黑窗口在加载模型…)")
        self._refresh_start_btn()

    def start_listen(self):
        _spawn("listen", console=False)
        self._set("✓ 测试模式已启动 (只听不发键)")

    def open_audio(self):
        _spawn("audio", console=False)
        self._set("✓ 已打开音频设置")

    def open_dict(self):
        _spawn("dict", console=False)
        self._set("✓ 已打开指令词典")

    def open_log(self):
        from paths import log_file
        p = log_file()
        if os.path.exists(p) and os.path.getsize(p) > 0:
            os.startfile(p)
            self._set("✓ 已打开日志 (出问题可把它发给作者)")
        else:
            self._set("日志还是空的 —— 先运行一次语音指挥再看", GOLD)

    def open_log_folder(self):
        from paths import log_dir
        os.startfile(log_dir())
        self._set("✓ 已打开日志文件夹 (把 app.log 发给作者即可)")

    def run_tests(self):
        # 测试是开发向工具, 打包版里不带; 源码下才拉起
        if FROZEN:
            self._set("测试仅在源码环境可用", GOLD)
            return
        exe = PY
        argv = [exe, os.path.join(ROOT, "tests", "run_all.py")]
        subprocess.Popen(argv, cwd=ROOT)
        self._set("✓ 测试已启动 (黑窗里看命中率+延迟)")

    def _refresh_start_btn(self):
        running = self.voice_proc and self.voice_proc.poll() is None
        if running:
            self.start_btn.config(text="■  语音指挥运行中", bg=GREEN)
        else:
            self.start_btn.config(text="▶  开始语音指挥", bg=GOLD)

    def _poll_voice(self):
        self._refresh_start_btn()
        self.root.after(1000, self._poll_voice)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    Launcher().run()
