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
RED = "#ff8a8a"


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


def _spawn(mode, console, job=None):
    """按 mode 拉起一个功能子进程。源码/打包两种形态都成立。

    console=True 的功能(语音/测试)要有黑窗看日志; GUI 无窗。
    job: KillOnCloseJob —— 传了就把子进程加进作业, 启动器一退它就跟着死,
    从根上杜绝"关了启动器、语音还在后台跑"。
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
    proc = subprocess.Popen(argv, cwd=ROOT, creationflags=flags)
    if job is not None:
        job.assign(proc.pid)
    return proc


class Launcher:
    def __init__(self):
        self.voice_proc = None
        self.lang = _read_language()
        i18n.set_lang(self.lang)
        # 作业对象: 本启动器拉起的所有子进程随本进程一起终结 (防后台残留)
        try:
            from procman import KillOnCloseJob
            self.job = KillOnCloseJob()
        except Exception:
            self.job = None
        self.root = tk.Tk()
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        self._build_ui()
        self.root.after(1000, self._poll_voice)
        # 首次启动: 有 N 卡却没装 CUDA 库 -> 主动引导下载(只问一次)。
        # 延后 600ms 让主窗口先画出来, 弹窗才有归属感。
        self.root.after(600, self._offer_gpu)

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
            (t("📜\n指令复盘"), t("看识别记录\n纠错改绑定"), self.open_review),
            (t("🎙\n音频设置"), t("选麦克风\n看音量条"), self.open_audio),
            (t("📖\n指令词典"), t("看/加说法\n改键位"), self.open_dict),
        ]
        btn_w = max(i18n.text_units(title) for title, _, _ in minis) + 2
        for title, sub, cmd in minis:
            self._mini(row, title, sub, cmd, btn_w)

        # 语音数据共建 (自愿): 勾选留存指令片段, 导出发给作者攒微调语料
        don = tk.Frame(self.root, bg=BG)
        don.pack(pady=(10, 0))
        self.don_var = tk.BooleanVar(value=self._donation_enabled())
        tk.Checkbutton(
            don, text=t("🎤 参与语音数据共建 (自愿, 只存指令片段)"),
            variable=self.don_var, command=self._toggle_donation,
            bg=BG, fg=FG, selectcolor="#1a2026", activebackground=BG,
            activeforeground=FG, font=("Microsoft YaHei", 9),
        ).pack(side="left")
        tk.Button(don, text=t("📦 导出数据包"), command=self.export_donation,
                  font=("Microsoft YaHei", 9), bg="#2a323a", fg=FG,
                  activebackground="#3a444e", relief="flat",
                  padx=10, pady=2).pack(side="left", padx=(10, 0))

        # 底部: 查看日志 (自己排错 / 发给作者)
        foot = tk.Frame(self.root, bg=BG)
        foot.pack(pady=(14, 4))
        tk.Button(foot, text=t("📋 查看日志"), command=self.open_log,
                  font=("Microsoft YaHei", 10), bg="#2a323a", fg=FG,
                  activebackground="#3a444e", relief="flat", padx=12, pady=3).pack(
            side="left", padx=5)
        tk.Button(foot, text=t("📦 打包日志 (报障用)"), command=self.pack_logs,
                  font=("Microsoft YaHei", 10), bg="#2a323a", fg=FG,
                  activebackground="#3a444e", relief="flat", padx=12, pady=3).pack(
            side="left", padx=5)
        tk.Button(foot, text=t("🛑 全部停止"), command=self.stop_all,
                  font=("Microsoft YaHei", 10), bg="#3a2a2a", fg=FG,
                  activebackground="#4a3030", relief="flat", padx=12, pady=3).pack(
            side="left", padx=5)

        self.status = tk.Label(self.root,
                               text=t("出问题？点「打包日志」，把生成的文件发给作者"),
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
        self.voice_proc = _spawn("voice", console=True, job=self.job)
        self._set(t("✓ 语音指挥已启动 (黑窗口在加载模型…)"))
        self._refresh_start_btn()

    def stop_all(self):
        """一键强杀所有语音进程 (排除本启动器) —— 兜底清残留。"""
        import procman
        n = procman.stop_all(exclude_pid=os.getpid())
        self.voice_proc = None
        self._refresh_start_btn()
        if n:
            self._set(t("🛑 已停止 {n} 个语音进程").format(n=n), GOLD)
        else:
            self._set(t("没有其它语音进程在跑 (已是干净状态)"))

    def start_calibrate(self):
        _spawn("calibrate", console=False, job=self.job)
        self._set(t("✓ 上手校准已启动 (跟着屏幕念)"))

    def start_listen(self):
        _spawn("listen", console=False, job=self.job)
        self._set(t("✓ 测试模式已启动 (只听不发键)"))

    def open_review(self):
        _spawn("review", console=False, job=self.job)
        self._set(t("✓ 已打开指令复盘 (游戏里也可按 F11 呼出)"))

    def _offer_gpu(self):
        """首次启动的 GPU 加速引导 (条件不满足则静默跳过, 绝不挡启动)。"""
        try:
            import gpu_setup
            if gpu_setup.offer_if_needed(self.root):
                self._set(t("检测到可用显卡 —— 见弹窗"), GOLD)
        except Exception:
            pass

    def pack_logs(self):
        """一键把日志打包成 zip —— 报障时用户直接把这个文件发给作者。

        小白找不到 %LOCALAPPDATA% 那串路径, 与其教路径不如给个按钮。
        只收诊断必需的三件: app.log(语音程序全过程) / mod.log(模组心跳) /
        usage.csv(每条指令一行, 最适合分析错配)。不含任何录音。
        """
        import zipfile
        from datetime import datetime
        from tkinter import messagebox
        from paths import log_dir
        from version import APP_VERSION

        d = log_dir()
        wanted = ["app.log", "mod.log", "usage.csv"]
        found = [f for f in wanted if os.path.exists(os.path.join(d, f))]
        if not found:
            self._set(t("还没有日志 (先运行一次语音指挥)"), DIM)
            return
        out = os.path.join(os.path.dirname(d),
                           f"日志-{APP_VERSION}-"
                           f"{datetime.now():%Y%m%d-%H%M}.zip")
        try:
            with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
                for f in found:
                    z.write(os.path.join(d, f), f)
                z.writestr("_版本.txt", f"APP_VERSION={APP_VERSION}\n")
        except Exception as e:
            self._set(t("导出失败: {e}").format(e=e), RED)
            return
        try:
            subprocess.Popen(["explorer", "/select,", out])
        except Exception:
            pass
        messagebox.showinfo(
            t("打包日志"),
            t("日志已打包(不含任何录音):\n{p}\n\n"
              "文件夹已打开并高亮它 —— 把这个文件发给作者即可。").format(p=out))
        self._set(t("✓ 日志已打包, 把高亮的文件发给作者"))

    # ---------- 语音数据共建 ----------

    def _donation_enabled(self):
        try:
            import yaml
            from paths import config_path
            with open(config_path("settings.yaml"), encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            return bool((cfg.get("data_donation") or {}).get("enabled", False))
        except Exception:
            return False

    def _toggle_donation(self):
        import donation
        from tkinter import messagebox
        want = self.don_var.get()
        if want:
            # 首次开启: 完整知情同意, 不同意就回退
            if not messagebox.askokcancel(t("语音数据共建"),
                                          t(donation.CONSENT_TEXT)):
                self.don_var.set(False)
                return
        try:
            from audio_setup import save_yaml_setting
            save_yaml_setting("data_donation", "enabled",
                              "true" if want else "false")
        except Exception as e:
            self.don_var.set(not want)
            self._set(t("切换失败: {e}").format(e=e), RED)
            return
        if want:
            self._set(t("✓ 已开启共建 (语音指挥运行中的话按 F10 生效)"))
        else:
            self._set(t("已关闭共建, 不再保存任何片段"))

    def _upload_url(self):
        try:
            import yaml
            from paths import config_path
            with open(config_path("settings.yaml"), encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            return ((cfg.get("data_donation") or {}).get("upload_url") or "").strip()
        except Exception:
            return ""

    def export_donation(self):
        import donation
        from tkinter import messagebox
        n, mb = donation.stats()
        if not n:
            self._set(t("还没有留存的片段 (先勾选共建并打几场)"), DIM)
            return
        try:
            p = donation.export_zip()
        except Exception as e:
            self._set(t("导出失败: {e}").format(e=e), RED)
            return
        try:      # 资源管理器里高亮这个 zip, 方便用户直接拖走
            import subprocess
            subprocess.Popen(["explorer", "/select,", p])
        except Exception:
            pass
        url = self._upload_url()
        if url:
            import webbrowser
            webbrowser.open(url)      # 自动打开收件箱网页
            messagebox.showinfo(
                t("上传数据包"),
                t("数据包已生成并在文件夹里高亮:\n{p}\n\n上传页已在浏览器打开 —— "
                  "把那个高亮的文件拖进网页即可 (不用登录)。\n\n"
                  "共 {n} 条 / {mb}MB。谢谢参与!").format(p=p, n=n, mb=mb))
            self._set(t("✓ 已导出并打开上传页, 把高亮文件拖进去即可"))
        else:
            self._set(t("✓ 数据包已导出 ({n}条/{mb}MB), 把它发给作者即可").format(
                n=n, mb=mb))

    def open_audio(self):
        _spawn("audio", console=False, job=self.job)
        self._set(t("✓ 已打开音频设置"))

    def open_dict(self):
        _spawn("dict", console=False, job=self.job)
        self._set(t("✓ 已打开指令词典"))

    def open_log(self):
        from paths import log_file
        p = log_file()
        if os.path.exists(p) and os.path.getsize(p) > 0:
            os.startfile(p)
            self._set(t("✓ 已打开日志 (出问题可把它发给作者)"))
        else:
            self._set(t("日志还是空的 —— 先运行一次语音指挥再看"), GOLD)

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
