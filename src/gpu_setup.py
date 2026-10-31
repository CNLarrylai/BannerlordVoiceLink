# -*- coding: utf-8 -*-
"""首次启动的两个引导弹窗 —— 共用一个对话框外壳, 各自只问一次。

  有 N 卡却没装 CUDA 库 -> GpuOfferDialog (下 1.2GB, 开 GPU 加速)
  没有可用 GPU     -> AccuracyOfferDialog (可选下 small 模型, 兜底更准)
    —— 0.9.11 起包里只内置 base(142MB) 不再内置 small(464MB), 所以要给
    无卡玩家一个一键把兜底准度补回来的入口。

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


GPU_FLAG = ".gpu_prompted"
ACC_FLAG = ".accuracy_prompted"


def _flag_path(name=GPU_FLAG):
    return os.path.join(user_data_dir(), name)


def already_prompted(name=GPU_FLAG):
    return os.path.exists(_flag_path(name))


def mark_prompted(name=GPU_FLAG):
    try:
        os.makedirs(user_data_dir(), exist_ok=True)
        with open(_flag_path(name), "w", encoding="utf-8") as f:
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


def should_offer_accuracy():
    """该不该弹"下 small 更准": 没有可用 GPU + small 还没有 + 没问过。

    有卡且 CUDA 齐的人用 turbo, small 对他们没意义, 不打扰。
    """
    if already_prompted(ACC_FLAG):
        return False
    try:
        from audio_setup import detect_gpu
        state, _why = detect_gpu()
        if state == "ready":
            return False
        from stt import model_available
        return not model_available("small")
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


class _OfferDialog:
    """引导对话框外壳: 说明 -> 下载(带进度) -> 完成提示。

    子类只需给文案和“下载做什么/下完做什么”。两个引导兼容一份外壳,
    改布局/修截断只用改一处 (tools/ui_audit.py 两个都会扫)。
    """
    FLAG = GPU_FLAG

    def title_text(self):
        raise NotImplementedError

    def heading_text(self):
        raise NotImplementedError

    def body_text(self):
        raise NotImplementedError

    def ok_text(self):
        raise NotImplementedError

    def do_download(self, on_prog):
        raise NotImplementedError

    def done_text(self):
        """返回下完之后要显示的一句话。"""
        raise NotImplementedError

    def __init__(self, master):
        self.q = queue.Queue()
        self.downloading = False
        self.win = tk.Toplevel(master)
        self.win.title(self.title_text())
        self.win.configure(bg=BG)
        self.win.resizable(False, False)
        self.win.transient(master)
        self.win.grab_set()

        tk.Label(self.win, text=self.heading_text(), bg=BG, fg=GOLD,
                 font=("Microsoft YaHei", 16, "bold")).pack(padx=30, pady=(22, 6))
        tk.Label(self.win, bg=BG, fg=FG, justify="left",
                 font=("Microsoft YaHei", 10),
                 text=self.body_text()).pack(padx=30, pady=(0, 14))

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
            row, text=self.ok_text(), command=self._start,
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
        mark_prompted(self.FLAG)
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
                self.do_download(lambda d, tot: self.q.put(("prog", (d, tot))))
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
                    mark_prompted(self.FLAG)
                    self.bar["value"] = 100
                    self.status.config(text=self.done_text(), fg=GREEN)
                    self.ok_btn.config(text=t("完成"), state="normal",
                                       command=self.win.destroy)
                    self.later_btn.destroy()
                elif kind == "err":
                    self.downloading = False
                    mark_prompted(self.FLAG)
                    self.ok_btn.config(state="normal")
                    self.later_btn.config(state="normal")
                    self.status.config(
                        text=t("下载失败: {e} (可稍后在音频设置里重试)").format(
                            e=str(payload)[:50]), fg=RED)
        except queue.Empty:
            pass
        if self.win.winfo_exists():
            self.win.after(200, self._poll)


class GpuOfferDialog(_OfferDialog):
    """有 N 卡却缺 CUDA 库: 下 1.2GB 开 GPU 加速。"""
    FLAG = GPU_FLAG

    def title_text(self):
        return t("发现你的显卡可以加速")

    def heading_text(self):
        return t("🚀 检测到 NVIDIA 显卡")

    def body_text(self):
        size = "≈ 1.2 GB"
        try:
            import cuda_libs
            size = cuda_libs.size_hint()
        except Exception:
            pass
        return t("你的显卡可以让语音识别又快又准, 但还缺一个 GPU 加速库\n"
                 "({size}, 一次性下载)。\n\n"
                 "下载后: 识别更准, 疑难指令的兜底速度从约 1.7 秒降到 0.2 秒。\n"
                 "不下载也完全能用 —— 现在走 CPU 档, 一样能指挥。").format(size=size)

    def ok_text(self):
        return t("⬇ 下载并启用 GPU 加速")

    def do_download(self, on_prog):
        import cuda_libs
        cuda_libs.download(on_prog)

    def done_text(self):
        return (t("✓ 已启用 GPU 加速, 识别模型已切到最强档")
                if apply_gpu_model() else
                t("✓ 下载完成 (模型档位请在音频设置里选)"))


class AccuracyOfferDialog(_OfferDialog):
    """没有可用 GPU: 可选下 small, 把兜底准度补回来。

    包里内置的是 base —— 日常识别走快路(0.1s), Whisper 只是兜底,
    所以不下也完全能用; 下了则兜底命中从 92% 到 100%。下完不用改设置:
    model=auto 会自动优先用已下载的 small (见 stt.resolve_stt_config)。
    """
    FLAG = ACC_FLAG

    def title_text(self):
        return t("可选: 让兜底识别更准")

    def heading_text(self):
        return t("🎯 想让识别再准一点吗?")

    def body_text(self):
        size = "≈ 464 MB"
        try:
            import models
            size = models.size_hint("small")
        except Exception:
            pass
        return t("没检测到可用的 N 卡, 你现在走 CPU 档 —— 日常指令由快路约 0.1 秒\n"
                 "直出, 完全能用。只有快路解不出的疑难句子才走兜底模型。\n\n"
                 "想把兜底也拉满, 可以下一个更大的兜底模型({size}, 一次性):\n"
                 "兜底命中率 92% → 100%, 代价是兜底耗时 0.6 秒 → 1.7 秒。\n"
                 "不下也没关系, 以后在「音频与模型设置」里随时可以下。").format(size=size)

    def ok_text(self):
        return t("⬇ 下载更准的兜底模型")

    def do_download(self, on_prog):
        import models
        models.download("small", on_prog)

    def done_text(self):
        return t("✓ 完成, 兜底模型已自动切成更准的那个")


def offer_if_needed(master):
    """启动器调这个: 满足条件才弹, 否则什么都不做。

    一次只弹一个: 有卡缺库优先引导 GPU(收益更大), 否则才问兜底模型。
    """
    try:
        if should_offer():
            return GpuOfferDialog(master)
        if should_offer_accuracy():
            return AccuracyOfferDialog(master)
    except Exception:
        pass
    return None
