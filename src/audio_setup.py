"""音频输入设置 GUI —— 选择语音指挥用哪一路麦克风。

每路输入设备旁有实时音量条: 对着麦克风说话, 看哪根条在跳, 选中它,
点「保存」即写入 config/settings.yaml 的 audio.device (存设备名)。

只列 WASAPI 设备 (名字完整、每个物理/虚拟设备只出现一次)。
"""
import os
import queue
import re
import sys
import threading
import tkinter as tk
from tkinter import ttk

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

import numpy as np
import sounddevice as sd
import yaml

from i18n import t, text_units  # noqa: E402
from paths import config_path  # noqa: E402

SETTINGS = config_path("settings.yaml")

BG = "#101418"
FG = "#e8edf2"
DIM = "#9aa4ad"
GOLD = "#d4af37"
GREEN = "#7dff9b"


def list_wasapi_inputs():
    """返回 [(index, name)] 的 WASAPI 输入设备列表。"""
    apis = sd.query_hostapis()
    out = []
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] <= 0:
            continue
        if "WASAPI" not in apis[d["hostapi"]]["name"]:
            continue
        out.append((i, d["name"]))
    return out


def current_saved_device():
    with open(SETTINGS, encoding="utf-8") as f:
        return (yaml.safe_load(f).get("audio") or {}).get("device")


def save_device(name):
    """把设备名写进 settings.yaml 的 audio.device 行 (保留文件里所有注释)。"""
    with open(SETTINGS, encoding="utf-8") as f:
        lines = f.readlines()
    in_audio = False
    for i, line in enumerate(lines):
        if re.match(r"^\S", line):                 # 顶层键
            in_audio = line.startswith("audio:")
        if in_audio and re.match(r"^\s+device\s*:", line):
            value = "null" if name is None else f'"{name}"'
            lines[i] = f"  device: {value}\n"
            break
    else:
        raise RuntimeError("settings.yaml 里没找到 audio.device 行")
    with open(SETTINGS, "w", encoding="utf-8") as f:
        f.writelines(lines)


def save_yaml_setting(section, key, value_str):
    """改写 settings.yaml 里 <section>.<key> 那一行 (保留其余注释)。"""
    with open(SETTINGS, encoding="utf-8") as f:
        lines = f.readlines()
    in_sec = False
    for i, line in enumerate(lines):
        if re.match(r"^\S", line):
            in_sec = line.startswith(section + ":")
        if in_sec and re.match(rf"^\s+{re.escape(key)}\s*:", line):
            lines[i] = f"  {key}: {value_str}\n"
            break
    else:
        raise RuntimeError(f"settings.yaml 里没找到 {section}.{key}")
    with open(SETTINGS, "w", encoding="utf-8") as f:
        f.writelines(lines)


def current_stt():
    with open(SETTINGS, encoding="utf-8") as f:
        s = yaml.safe_load(f).get("stt") or {}
    return str(s.get("model", "auto")), str(s.get("device", "auto"))


def current_control():
    with open(SETTINGS, encoding="utf-8") as f:
        c = yaml.safe_load(f).get("control") or {}
    mode = c.get("mode", "continuous")
    if mode not in LISTEN_MODES:
        mode = "continuous"
    return {"mode": mode,
            "toggle": c.get("listen_toggle_key") or "left alt",
            "push_to_talk": c.get("push_to_talk_key") or "caps lock",
            "taken": [c.get("reload_key"), c.get("review_key")]}


# 监听模式: (配置值, 按钮文字, 说明)。按钮文字刻意短(英文宽 30~100%)。
LISTEN_MODES = {
    "continuous": ("一直监听", "说话就识别, 不占任何按键"),
    "toggle": ("按键开关", "轻点一下开始听, 再点一下停; 启动时是关的"),
    "push_to_talk": ("按住说话", "按住键说话, 松开识别"),
}


def detect_gpu():
    """探测 GPU 三态。返回 (状态, 说明)。

    状态: "ready" 有N卡且CUDA可用 | "need_cuda" 有N卡但缺CUDA库(可下载)
          | "no_gpu" 没有可用N卡。
    """
    try:
        import ctranslate2
        n = ctranslate2.get_cuda_device_count()
    except Exception:
        n = 0
    try:
        import cuda_libs
        libs = cuda_libs.is_ready()
    except Exception:
        libs = False
    if n > 0 and libs:
        return "ready", t("✓ 检测到 NVIDIA 显卡, CUDA 可用 (可用 GPU 加速)")
    if n > 0:
        return "need_cuda", t("检测到 N 卡但缺 CUDA 库 → 下载后即可 GPU 加速")
    return "no_gpu", t("未检测到可用 GPU → 用 CPU 运行")


def _cuda_size():
    try:
        import cuda_libs
        return cuda_libs.size_hint()
    except Exception:
        return "≈ 1.2 GB"


def model_status(size):
    """base/small… 这个模型: 内置 / 已下载 / 需联网下载。

    就绪判断交给 models.is_ready (按真实仓库名查缓存 —— turbo 在
    mobiuslabsgmbh 而非 Systran, 硬拼路径会误报"需下载")。
    """
    from paths import bundle_dir
    if os.path.isdir(os.path.join(bundle_dir(), "models", f"faster-whisper-{size}")):
        return t("内置")
    import models
    return t("已下载") if models.is_ready(size) else t("需联网下载")


# 模型选项: (值, 显示名, 提示)
MODEL_OPTS = [
    ("auto", "自动", "跟随硬件自动选 (推荐)"),
    ("tiny", "tiny", "最快 · 准度偏低"),
    ("base", "base", "快 · 够用 (推荐)"),
    ("small", "small", "更准 · 稍慢"),
    ("medium", "medium", "很准 · 明显慢"),
    ("large-v3-turbo", "large-v3-turbo", "≈最准 · 较快 (推荐给N卡)"),
    ("large-v3", "large-v3", "最准 · 最慢"),
]
DEVICE_OPTS = [
    ("auto", "自动 (推荐)"),
    ("cuda", "强制 GPU"),
    ("cpu", "强制 CPU"),
]


class Meter:
    """单个设备的实时音量表: 打开输入流, 记录最近 RMS。"""

    def __init__(self, index):
        self.rms = 0.0
        self.ok = True
        try:
            info = sd.query_devices(index)
            sr = int(info["default_samplerate"])
            self.stream = sd.InputStream(
                samplerate=sr, channels=1, dtype="float32", device=index,
                blocksize=int(sr * 0.05), callback=self._cb,
            )
            self.stream.start()
        except Exception:
            self.ok = False
            self.stream = None

    def _cb(self, indata, frames, time_info, status):
        self.rms = float(np.sqrt(np.mean(indata ** 2)))

    def close(self):
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass


class SetupWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(t("音频与识别设置 — 骑砍语音指挥"))
        self.root.configure(bg=BG)
        self.root.attributes("-topmost", True)

        tk.Label(
            self.root, text=t("⚙ 音频与识别设置"),
            fg=GOLD, bg=BG, font=("Microsoft YaHei", 14, "bold"),
        ).pack(padx=24, pady=(16, 8))

        # status 标签必须在引擎区之前"创建"(引擎区的 CPU 大模型警告会写它;
        # 曾因创建顺序在后, 打包版CPU机器一进音频设置就崩), 但按原布局稍后 pack。
        self.status = tk.Label(self.root, text="", fg=GREEN, bg=BG,
                               font=("Microsoft YaHei", 11))

        self._build_engine_section()
        self._build_listen_section()

        tk.Label(
            self.root, text=t("🎙 麦克风：对着说话，看哪根音量条在跳，选中它，点保存"),
            fg=GOLD, bg=BG, font=("Microsoft YaHei", 12, "bold"),
        ).pack(padx=24, pady=(4, 2))
        tk.Label(
            self.root, text=t("绿色条 = 有声音进来。选中后建议再说几句确认就是这一路。"),
            fg=DIM, bg=BG, font=("Microsoft YaHei", 9),
        ).pack(padx=24, pady=(0, 10))

        style = ttk.Style(self.root)
        style.theme_use("default")
        style.configure(
            "level.Horizontal.TProgressbar",
            troughcolor="#1c2228", background=GREEN, thickness=14,
        )

        self.selected = tk.StringVar(value="")
        saved = current_saved_device()

        frame = tk.Frame(self.root, bg=BG)
        frame.pack(padx=24, pady=4, fill="both", expand=True)

        self.devices = list_wasapi_inputs()
        self.meters = {}
        self.bars = {}

        # "系统默认" 选项
        self._add_row(frame, 0, None, t("系统默认设备"), saved is None)
        for row, (idx, name) in enumerate(self.devices, start=1):
            self._add_row(frame, row, idx, name, saved == name)
            self.meters[idx] = Meter(idx)

        self.status.pack(pady=(8, 0))   # 创建在引擎区之前, 布局位置不变

        btns = tk.Frame(self.root, bg=BG)
        btns.pack(pady=(6, 18))
        tk.Button(
            btns, text=t("💾 保存并使用这一路"), command=self.save,
            font=("Microsoft YaHei", 12, "bold"), bg=GOLD, fg="#101418",
            activebackground="#e8c95a", relief="flat", padx=18, pady=6,
        ).pack(side="left", padx=8)
        tk.Button(
            btns, text=t("关闭"), command=self.close,
            font=("Microsoft YaHei", 12), bg="#2a323a", fg=FG,
            activebackground="#3a444e", relief="flat", padx=18, pady=6,
        ).pack(side="left", padx=8)

        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(80, self._tick)

    def _build_engine_section(self):
        eng = tk.Frame(self.root, bg="#161c22", highlightthickness=1,
                       highlightbackground="#2a323a")
        eng.pack(padx=24, pady=(0, 8), fill="x")

        tk.Label(eng, text=t("🧠 识别引擎"), fg=GOLD, bg="#161c22",
                 font=("Microsoft YaHei", 12, "bold")).grid(
            row=0, column=0, columnspan=4, sticky="w", padx=12, pady=(10, 2))

        gpu_state, hw = detect_gpu()
        hwrow = tk.Frame(eng, bg="#161c22")
        hwrow.grid(row=1, column=0, columnspan=4, sticky="ew", padx=12, pady=(0, 6))
        hwrow.columnconfigure(0, weight=1)
        gpu_col = GREEN if gpu_state == "ready" else (
            "#ffcf70" if gpu_state == "need_cuda" else DIM)
        tk.Label(hwrow, text=hw, fg=gpu_col, bg="#161c22",
                 font=("Microsoft YaHei", 9), anchor="w").grid(
            row=0, column=0, sticky="w")
        # 有 N 卡但缺 CUDA -> 给一键下载 GPU 加速库
        self.cuda_q = queue.Queue()
        self.cuda_downloading = False
        cudabtns = tk.Frame(hwrow, bg="#161c22")
        self.cuda_btnrow = cudabtns
        self.cuda_browse = tk.Button(
            cudabtns, text=t("📁 已有?指定文件夹"), command=self._browse_cuda,
            font=("Microsoft YaHei", 9), bg="#2a323a", fg=FG, relief="flat",
            padx=8)
        self.cuda_browse.pack(side="left", padx=(0, 6))
        self.cuda_btn = tk.Button(
            cudabtns, text=t("⬇ 下载 ({size})").format(size=_cuda_size()),
            command=self._download_cuda,
            font=("Microsoft YaHei", 9), bg=GOLD, fg="#101418", relief="flat",
            padx=10)
        self.cuda_btn.pack(side="left")
        if gpu_state == "need_cuda":
            cudabtns.grid(row=0, column=1, sticky="e")
        self.cuda_bar = ttk.Progressbar(hwrow, style="level.Horizontal.TProgressbar",
                                        length=380, maximum=100)
        self.cuda_bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        self.cuda_bar.grid_remove()

        cur_model, cur_device = current_stt()
        self._stt_before = (cur_model, cur_device)

        tk.Label(eng, text=t("模型:"), fg=FG, bg="#161c22",
                 font=("Microsoft YaHei", 10)).grid(
            row=2, column=0, sticky="e", padx=(12, 4), pady=(0, 10))
        self.model_map = {}
        mvals = []
        for val, disp, hint in MODEL_OPTS:
            disp = t(disp)
            tag = disp if val == "auto" else f"{disp} · {model_status(val)}"
            label = f"{tag}   — {t(hint)}"
            self.model_map[label] = val
            mvals.append(label)
        # 宽度按当前语言最长条目算 (i18n: 不写死字符宽), 上限防止窗口过宽。
        # 上限 64: 新用户状态下所有档位都是 "needs download"(比 downloaded 长),
        # 英文最长条目 61 字符, 58 会截断(2026-09-09 新用户模拟 ui_audit 抓到)
        mbox_w = min(64, max(text_units(v) for v in mvals) + 2)
        self.model_box = ttk.Combobox(eng, state="readonly", values=mvals,
                                      font=("Microsoft YaHei", 10), width=mbox_w)
        self.model_box.grid(row=2, column=1, sticky="w", pady=(0, 10))
        self.model_box.set(next((lb for lb, v in self.model_map.items()
                                 if v == cur_model), mvals[0]))

        tk.Label(eng, text=t("运行:"), fg=FG, bg="#161c22",
                 font=("Microsoft YaHei", 10)).grid(
            row=2, column=2, sticky="e", padx=(16, 4), pady=(0, 10))
        self.device_map = {t(disp): val for val, disp in DEVICE_OPTS}
        dbox_w = max(text_units(v) for v in self.device_map) + 2
        self.device_box = ttk.Combobox(
            eng, state="readonly", values=list(self.device_map.keys()),
            font=("Microsoft YaHei", 10), width=dbox_w)
        self.device_box.grid(row=2, column=3, sticky="w", padx=(0, 12), pady=(0, 10))
        self.device_box.set(next((d for d, v in self.device_map.items()
                                  if v == cur_device), t(DEVICE_OPTS[0][1])))
        self.model_box.bind("<<ComboboxSelected>>", self._on_model_change)

        # 下载状态 + 按钮
        self.dl_q = queue.Queue()
        self.downloading = False
        dl = tk.Frame(eng, bg="#161c22")
        dl.grid(row=3, column=0, columnspan=4, sticky="ew", padx=12, pady=(0, 4))
        dl.columnconfigure(0, weight=1)
        self.dl_status = tk.Label(dl, text="", bg="#161c22", fg=DIM,
                                  font=("Microsoft YaHei", 9), anchor="w", justify="left")
        self.dl_status.grid(row=0, column=0, sticky="w")
        self.dl_btn = tk.Button(dl, text=t("⬇ 下载所选模型"),
                                command=self._download_model,
                                font=("Microsoft YaHei", 9), bg=GOLD, fg="#101418",
                                relief="flat", padx=12)
        self.dl_btn.grid(row=0, column=1, sticky="e")
        self.dl_bar = ttk.Progressbar(dl, style="level.Horizontal.TProgressbar",
                                      length=380, maximum=100)
        # 进度条按需显示 (grid_remove 先藏起来)
        self.dl_bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        self.dl_bar.grid_remove()

        tk.Label(eng,
                 text=t("改了模型 / 运行方式后，重启语音指挥生效。"),
                 fg=DIM, bg="#161c22", font=("Microsoft YaHei", 9),
                 anchor="w").grid(row=4, column=0, columnspan=4, sticky="w",
                                  padx=12, pady=(2, 10))
        self._on_model_change()
        self.root.after(120, self._dl_poll)
        self.root.after(140, self._cuda_poll)

    # ---------- 监听方式: 一直监听 / 按键开关 / 按住说话 + 改键 ----------
    def _build_listen_section(self):
        import hotkeys
        self._hotkeys = hotkeys
        PANEL = "#161c22"
        box = tk.Frame(self.root, bg=PANEL, highlightthickness=1,
                       highlightbackground="#2a323a")
        box.pack(padx=24, pady=(0, 8), fill="x")
        tk.Label(box, text=t("🎧 监听方式"), fg=GOLD, bg=PANEL,
                 font=("Microsoft YaHei", 12, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(10, 4))

        ctl = current_control()
        self._ctl_before = dict(ctl)
        self.keys = {"toggle": ctl["toggle"], "push_to_talk": ctl["push_to_talk"]}
        self._taken = [k for k in ctl["taken"] if k]
        self.listen_mode = tk.StringVar(value=ctl["mode"])

        row = tk.Frame(box, bg=PANEL)
        row.grid(row=1, column=0, columnspan=2, sticky="w", padx=12)
        for val, (label, _) in LISTEN_MODES.items():
            tk.Radiobutton(row, text=t(label), value=val, variable=self.listen_mode,
                           command=self._on_listen_mode, fg=FG, bg=PANEL,
                           selectcolor="#101418", activebackground=PANEL,
                           activeforeground=FG, font=("Microsoft YaHei", 11),
                           ).pack(side="left", padx=(0, 16))

        self.listen_hint = tk.Label(box, text="", fg=DIM, bg=PANEL,
                                    font=("Microsoft YaHei", 9), anchor="w", justify="left")
        self.listen_hint.grid(row=2, column=0, columnspan=2, sticky="w", padx=12, pady=(4, 0))

        self.key_row = tk.Frame(box, bg=PANEL)
        self.key_row.grid(row=3, column=0, columnspan=2, sticky="w", padx=12, pady=(6, 10))
        tk.Label(self.key_row, text=t("按键:"), fg=FG, bg=PANEL,
                 font=("Microsoft YaHei", 10)).pack(side="left")
        self.key_lbl = tk.Label(self.key_row, text="", fg="#101418", bg=GOLD,
                                font=("Microsoft YaHei", 10, "bold"), padx=8)
        self.key_lbl.pack(side="left", padx=(6, 8))
        self.key_btn = tk.Button(self.key_row, text=t("修改…"), command=self._capture_key,
                                 font=("Microsoft YaHei", 9), bg="#2a323a", fg=FG,
                                 activebackground="#3a444e", relief="flat", padx=10)
        self.key_btn.pack(side="left")
        self.key_msg = tk.Label(self.key_row, text="", fg=DIM, bg=PANEL,
                                font=("Microsoft YaHei", 9))
        self.key_msg.pack(side="left", padx=(8, 0))
        self._capturing = False
        self._on_listen_mode()

    def _on_listen_mode(self):
        mode = self.listen_mode.get()
        self.listen_hint.config(text=t(LISTEN_MODES[mode][1]))
        if mode == "continuous":
            self.key_row.grid_remove()
        else:
            self.key_row.grid()
            self.key_lbl.config(text=self._hotkeys.pretty(self.keys[mode]))
            self.key_msg.config(text="", fg=DIM)

    def _capture_key(self):
        if self._capturing:
            return
        self._capturing = True
        self.key_lbl.config(text="…")
        self.key_msg.config(text=t("请按下新按键 (Esc 取消)"), fg="#7Fd1ff")
        self.root.focus_force()
        self.root.bind("<KeyPress>", self._on_key_captured)

    def _on_key_captured(self, event):
        self.root.unbind("<KeyPress>")
        self._capturing = False
        mode = self.listen_mode.get()
        if event.keysym == "Escape":
            self._on_listen_mode()
            return "break"
        key = self._hotkeys.from_tk(event.keysym)
        # 按键模式和按住说话同一时间只用一个, 两者用同一个键不算冲突
        why = self._hotkeys.reject_reason(key, taken=self._taken)
        if why:
            self.key_lbl.config(text=self._hotkeys.pretty(self.keys[mode]))
            self.key_msg.config(text=t(why), fg="#ff8a8a")
            return "break"
        self.keys[mode] = key
        self.key_lbl.config(text=self._hotkeys.pretty(key))
        self.key_msg.config(text=t("点「保存」生效"), fg=DIM)
        return "break"      # Alt 等键别再触发窗口菜单

    def _save_listen(self):
        mode = self.listen_mode.get()
        save_yaml_setting("control", "mode", mode)
        save_yaml_setting("control", "listen_toggle_key", f'"{self.keys["toggle"]}"')
        save_yaml_setting("control", "push_to_talk_key", f'"{self.keys["push_to_talk"]}"')
        return mode

    # ---------- CUDA 加速库: 指定已有 / 下载 ----------

    def _browse_cuda(self):
        """让用户选一个已有 CUDA 库的文件夹, 验证后登记、免下载。"""
        from tkinter import filedialog
        import cuda_libs
        folder = filedialog.askdirectory(
            title=t("选择含 cuBLAS/cuDNN 的文件夹 (如 …\\nvidia)"))
        if not folder:
            return
        ok, hits = cuda_libs.add_user_dir(folder)
        if ok:
            self.cuda_btnrow.grid_remove()
            self.status.config(
                text=t("✓ 已认到本地 CUDA 库，无需下载！运行选「自动/GPU」并重启即可"),
                fg=GREEN)
        elif hits:
            self.status.config(
                text=t("这里只找到部分 CUDA 库，缺 cuBLAS 或 cuDNN；换个更全的文件夹或直接下载"),
                fg="#ffcf70")
        else:
            self.status.config(
                text=t("该文件夹(含子目录)里没找到 CUDA 库(cublas64_12.dll / cudnn64_9.dll)"),
                fg="#ff8a8a")

    def _download_cuda(self):
        import cuda_libs
        if self.cuda_downloading:
            return
        self.cuda_downloading = True
        self.cuda_btn.config(state="disabled")
        self.cuda_bar.grid()
        self.cuda_bar["value"] = 0
        self.status.config(text=t("正在下载 GPU 加速库…（约 1.2GB，一次性）"),
                           fg="#7Fd1ff")

        def work():
            try:
                cuda_libs.download(lambda d, tot: self.cuda_q.put(("prog", (d, tot))))
                self.cuda_q.put(("done", None))
            except Exception as e:
                self.cuda_q.put(("err", str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _cuda_poll(self):
        try:
            while True:
                kind, payload = self.cuda_q.get_nowait()
                if kind == "prog":
                    d, tot = payload
                    pct = min(100, d / tot * 100) if tot else 0
                    self.cuda_bar["value"] = pct
                    self.status.config(
                        text=t("下载 GPU 加速库… {pct}%  ({d} / {t} MB)").format(
                            pct=f"{pct:.0f}", d=f"{d/1048576:.0f}",
                            t=f"{tot/1048576:.0f}" if tot else "?"), fg="#7Fd1ff")
                elif kind == "done":
                    self.cuda_downloading = False
                    self.cuda_bar.grid_remove()
                    self.cuda_btnrow.grid_remove()
                    self.status.config(
                        text=t("✓ GPU 加速库已就绪！运行选「自动/GPU」并重启语音指挥即可"),
                        fg=GREEN)
                elif kind == "err":
                    self.cuda_downloading = False
                    self.cuda_btn.config(state="normal")
                    self.cuda_bar.grid_remove()
                    self.status.config(
                        text=t("GPU 加速库下载失败: {e}").format(e=str(payload)[:60]),
                        fg="#ff8a8a")
        except queue.Empty:
            pass
        self.root.after(150, self._cuda_poll)

    def _selected_model(self):
        return self.model_map.get(self.model_box.get())

    @staticmethod
    def _effective(mv):
        return "base" if mv in (None, "", "auto") else mv

    def _on_model_change(self, event=None):
        import models
        mv = self._selected_model()
        eff = self._effective(mv)
        # CPU 跑大模型 = 每句好几秒, 体验像"坏了" —— 当场提醒
        gpu_ok, _ = detect_gpu()
        forced_cpu = self.device_map.get(self.device_box.get()) == "cpu" \
            if hasattr(self, "device_box") else False
        if (not gpu_ok or forced_cpu) and eff in ("medium", "large-v3",
                                                  "large-v3-turbo"):
            self.status.config(
                text=t("⚠ CPU 上跑 {m} 会很慢(每句数秒), 无独显强烈建议 base")
                .format(m=eff), fg="#ffcf70")
        if models.is_ready(eff):
            self.dl_status.config(
                text=t("✓ {m} 已就绪（本地已有，直接用）").format(m=mv), fg=GREEN)
            self.dl_btn.grid_remove()
        else:
            self.dl_status.config(
                text=t("⚠ {m} 未下载（{size}）—— 点右边下载").format(
                    m=mv, size=models.size_hint(eff)),
                fg="#ffcf70")
            self.dl_btn.grid()
        self.dl_bar.grid_remove()

    def _download_model(self):
        import models
        if self.downloading:
            return
        mv = self._selected_model()
        eff = self._effective(mv)
        if models.is_ready(eff):
            self._on_model_change()
            return
        self.downloading = True
        self.dl_btn.config(state="disabled")
        self.dl_bar.grid()
        self.dl_bar["value"] = 0
        self.dl_status.config(text=t("正在下载 {m} …").format(m=mv), fg="#7Fd1ff")

        def work():
            try:
                models.download(eff, lambda d, t: self.dl_q.put(("prog", (d, t))))
                self.dl_q.put(("done", mv))
            except Exception as e:
                self.dl_q.put(("err", e))

        threading.Thread(target=work, daemon=True).start()

    def _dl_poll(self):
        try:
            while True:
                kind, payload = self.dl_q.get_nowait()
                if kind == "prog":
                    d, tot = payload
                    if tot:
                        pct = min(100, d / tot * 100)
                        self.dl_bar["value"] = pct
                        self.dl_status.config(
                            text=t("下载中… {pct}%  ({d} / {t} MB)").format(
                                pct=f"{pct:.0f}", d=f"{d/1048576:.0f}",
                                t=f"{tot/1048576:.0f}"), fg="#7Fd1ff")
                    else:
                        self.dl_bar["value"] = 0
                        self.dl_status.config(
                            text=t("下载中… 已下 {d} MB").format(
                                d=f"{d/1048576:.0f}"), fg="#7Fd1ff")
                elif kind == "done":
                    self.downloading = False
                    self.dl_btn.config(state="normal")
                    self._on_model_change()
                    self.status.config(
                        text=t("✓ {m} 下载完成，已就绪").format(m=payload), fg=GREEN)
                elif kind == "err":
                    self.downloading = False
                    self.dl_btn.config(state="normal")
                    self.dl_bar.grid_remove()
                    # ModelDownloadError 的文案本身就是给用户的一句话, 整句显示;
                    # 其它异常截短(hub 库的英文长篇对小白没意义)
                    import models
                    msg = str(payload)
                    if not isinstance(payload, models.ModelDownloadError):
                        msg = msg[:60]
                    # 整句失败文案要折行(wraplength 只在这时设: 建窗时设会让空标签
                    # 的需求宽度撑到 540, ui_audit 判成截断)
                    self.dl_status.config(text=t("下载失败: {e}").format(e=msg),
                                          fg="#ff8a8a", wraplength=540)
        except queue.Empty:
            pass
        self.root.after(150, self._dl_poll)

    def _add_row(self, parent, row, idx, name, selected):
        val = name if idx is not None else "__default__"
        rb = tk.Radiobutton(
            parent, text=name, variable=self.selected, value=val,
            fg=FG, bg=BG, selectcolor="#1c2228", activebackground=BG,
            activeforeground=GOLD, font=("Microsoft YaHei", 11), anchor="w",
        )
        rb.grid(row=row, column=0, sticky="w", pady=3)
        if selected:
            self.selected.set(val)
        if idx is not None:
            bar = ttk.Progressbar(
                parent, style="level.Horizontal.TProgressbar",
                length=220, maximum=100,
            )
            bar.grid(row=row, column=1, padx=(16, 0), pady=3)
            self.bars[idx] = bar

    def _tick(self):
        for idx, meter in self.meters.items():
            bar = self.bars[idx]
            if not meter.ok:
                bar["value"] = 0
                continue
            level = min(100.0, meter.rms * 600)
            # 峰值缓降, 视觉上更好读
            bar["value"] = max(level, bar["value"] * 0.75)
        self.root.after(80, self._tick)

    def save(self):
        sel = self.selected.get()
        if not sel:
            self.status.config(text=t("先选一个麦克风设备再保存"), fg="#ff8a8a")
            return
        name = None if sel == "__default__" else sel
        try:
            save_device(name)
            mv = self.model_map.get(self.model_box.get())
            dv = self.device_map.get(self.device_box.get())
            if mv:
                save_yaml_setting("stt", "model", mv)
            if dv:
                save_yaml_setting("stt", "device", dv)
            mode = self._save_listen()
        except Exception as e:
            self.status.config(text=t("保存失败: {e}").format(e=e), fg="#ff8a8a")
            return
        import telemetry        # 埋点: 玩家把设置改成了什么(不记麦克风名, 可能含个人信息)
        b = self._ctl_before
        telemetry.track_changes(
            {"listen_mode": b["mode"], "toggle_key": b["toggle"],
             "push_to_talk_key": b["push_to_talk"], "model": self._stt_before[0],
             "stt_device": self._stt_before[1]},
            {"listen_mode": mode, "toggle_key": self.keys["toggle"],
             "push_to_talk_key": self.keys["push_to_talk"], "model": mv, "stt_device": dv})
        self._ctl_before = {"mode": mode, "toggle": self.keys["toggle"],
                            "push_to_talk": self.keys["push_to_talk"], "taken": self._taken}
        self._stt_before = (mv, dv)
        shown = t("系统默认") if name is None else name
        self.status.config(
            text=t("✓ 已保存 · 麦克风:{mic} · 模型:{m} · 运行:{d}   "
                   "(重启语音指挥后生效)").format(mic=shown, m=mv, d=dv), fg=GREEN)

    def close(self):
        for m in self.meters.values():
            m.close()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    SetupWindow().run()
