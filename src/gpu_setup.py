# -*- coding: utf-8 -*-
"""首次启动的 GPU 加速引导 —— 有 N 卡却没装 CUDA 库的人, 主动问一次。

背景: 包不含 CUDA 运行库(1.2GB), 所以"有独显"≠"在用 GPU"。旧版只在音频设置
里藏了个下载按钮, 粉丝根本不知道自己少装了库, 默默用着 CPU 档。
这里在启动器首次出现时主动检测并引导, 下完自动把模型档位切到 large-v3-turbo。

只问一次: 问过就写 gpu_prompted 标记(用户选"以后再说"也不再烦他);
音频设置里的下载入口保留, 随时可以自己去下。
"""
import os
import queue
import threading
import tkinter as tk

from i18n import t
from paths import user_data_dir

BG = "#101418"
FG = "#e8edf2"
DIM = "#9aa4ad"
GOLD = "#d4af37"
GREEN = "#7dff9b"
RED = "#ff8a8a"


def _flag_path():
    return os.path.join(user_data_dir(), ".gpu_prompted")


def already_prompted():
    return os.path.exists(_flag_path())


def mark_prompted():
    try:
        os.makedirs(user_data_dir(), exist_ok=True)
        with open(_flag_path(), "w", encoding="utf-8") as f:
            f.write("asked\n")
    except Exception:
        pass


def should_offer():
    """该不该弹引导: 有 N 卡 + 缺 CUDA 库 + 没问过。"""
    if already_prompted():
        return False
    try:
        from audio_setup import detect_gpu
        state, _why = detect_gpu()
        return state == "need_cuda"
    except Exception:
        return False


def apply_gpu_model():
    """下载完成后把模型档位切到 turbo(auto 也会自动走 turbo, 这里显式写死
    更直观, 用户在音频设置里能看到自己现在用的是什么)。"""
    try:
        from audio_setup import save_yaml_setting
        save_yaml_setting("stt", "model", "large-v3-turbo")
        save_yaml_setting("stt", "device", "auto")
        return True
    except Exception:
        return False


class GpuOfferDialog:
    """一个自包含的引导对话框: 说明 -> 下载(带进度) -> 完成提示。"""

    def __init__(self, master):
        self.q = queue.Queue()
        self.downloading = False
        self.win = tk.Toplevel(master)
        self.win.title(t("发现你的显卡可以加速"))
        self.win.configure(bg=BG)
        self.win.resizable(False, False)
        self.win.transient(master)
        self.win.grab_set()

        size = "≈ 1.2 GB"
        try:
            import cuda_libs
            size = cuda_libs.size_hint()
        except Exception:
            pass

        tk.Label(self.win, text=t("🚀 检测到 NVIDIA 显卡"), bg=BG, fg=GOLD,
                 font=("Microsoft YaHei", 16, "bold")).pack(padx=30, pady=(22, 6))
        tk.Label(
            self.win, bg=BG, fg=FG, justify="left",
            font=("Microsoft YaHei", 10),
            text=t("你的显卡可以让语音识别又快又准, 但还缺一个 GPU 加速库\n"
                   "({size}, 一次性下载)。\n\n"
                   "下载后: 识别更准, 疑难指令的兜底速度从约 1.7 秒降到 0.2 秒。\n"
                   "不下载也完全能用 —— 现在走 CPU 档, 一样能指挥。").format(size=size)
        ).pack(padx=30, pady=(0, 14))

        self.bar = tk.ttk.Progressbar(self.win, length=380, mode="determinate") \
            if hasattr(tk, "ttk") else None
        if self.bar is None:
            from tkinter import ttk
            self.bar = ttk.Progressbar(self.win, length=380, mode="determinate")
        self.bar.pack(padx=30)
        self.bar.pack_forget()

        self.status = tk.Label(self.win, text="", bg=BG, fg=DIM,
                               font=("Microsoft YaHei", 9))
        self.status.pack(padx=30, pady=(0, 8))

        row = tk.Frame(self.win, bg=BG)
        row.pack(padx=30, pady=(0, 22))
        self.ok_btn = tk.Button(
            row, text=t("⬇ 下载并启用 GPU 加速"), command=self._start,
            font=("Microsoft YaHei", 11, "bold"), bg=GOLD, fg="#101418",
            activebackground="#e8c95a", relief="flat", padx=16, pady=6)
        self.ok_btn.pack(side="left", padx=6)
        self.later_btn = tk.Button(
            row, text=t("以后再说"), command=self._later,
            font=("Microsoft YaHei", 10), bg="#2a323a", fg=FG,
            activebackground="#3a444e", relief="flat", padx=14, pady=6)
        self.later_btn.pack(side="left", padx=6)

        self.win.protocol("WM_DELETE_WINDOW", self._later)
        self.win.after(120, self._poll)

    def _later(self):
        if self.downloading:      # 下载中不让关, 免得下一半不知所措
            return
        mark_prompted()
        self.win.destroy()

    def _start(self):
        if self.downloading:
            return
        self.downloading = True
        self.ok_btn.config(state="disabled")
        self.later_btn.config(state="disabled")
        self.bar.pack(padx=30, pady=(0, 6))
        self.bar["value"] = 0
        self.status.config(text=t("正在下载… 可以先去玩, 下完会提示"), fg="#7Fd1ff")

        def work():
            try:
                import cuda_libs
                cuda_libs.download(lambda d, tot: self.q.put(("prog", (d, tot))))
                self.q.put(("done", None))
            except Exception as e:
                self.q.put(("err", str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _poll(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "prog":
                    d, tot = payload
                    pct = min(100, d / tot * 100) if tot else 0
                    self.bar["value"] = pct
                    self.status.config(
                        text=t("下载中 {pct}%  ({d} / {t} MB)").format(
                            pct=f"{pct:.0f}", d=f"{d/1048576:.0f}",
                            t=f"{tot/1048576:.0f}" if tot else "?"), fg="#7Fd1ff")
                elif kind == "done":
                    self.downloading = False
                    mark_prompted()
                    ok = apply_gpu_model()
                    self.bar["value"] = 100
                    self.status.config(
                        text=(t("✓ 已启用 GPU 加速, 识别模型已切到最强档")
                              if ok else
                              t("✓ 下载完成 (模型档位请在音频设置里选)")), fg=GREEN)
                    self.ok_btn.config(text=t("完成"), state="normal",
                                       command=self.win.destroy)
                    self.later_btn.destroy()
                elif kind == "err":
                    self.downloading = False
                    mark_prompted()
                    self.ok_btn.config(state="normal")
                    self.later_btn.config(state="normal")
                    self.status.config(
                        text=t("下载失败: {e} (可稍后在音频设置里重试)").format(
                            e=str(payload)[:50]), fg=RED)
        except queue.Empty:
            pass
        if self.win.winfo_exists():
            self.win.after(200, self._poll)


def offer_if_needed(master):
    """启动器调这个: 满足条件才弹, 否则什么都不做。"""
    if not should_offer():
        return None
    try:
        return GpuOfferDialog(master)
    except Exception:
        return None
