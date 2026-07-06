"""音频输入设置 GUI —— 选择语音指挥用哪一路麦克风。

每路输入设备旁有实时音量条: 对着麦克风说话, 看哪根条在跳, 选中它,
点「保存」即写入 config/settings.yaml 的 audio.device (存设备名)。

只列 WASAPI 设备 (名字完整、每个物理/虚拟设备只出现一次)。
"""
import os
import re
import sys
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


def detect_gpu():
    """轻量探测能否真正用 GPU (不加载 faster-whisper)。返回 (可用, 说明)。"""
    try:
        import ctranslate2
        n = ctranslate2.get_cuda_device_count()
    except Exception:
        n = 0
    try:
        import nvidia.cublas  # noqa: F401
        import nvidia.cudnn   # noqa: F401
        libs = True
    except Exception:
        libs = False
    if n > 0 and libs:
        return True, "✓ 检测到 NVIDIA 显卡, CUDA 可用 (可用 GPU 加速)"
    if n > 0:
        return False, "检测到显卡但缺 CUDA 运行库 → 本版本只能用 CPU"
    return False, "未检测到可用 GPU → 用 CPU 运行"


def model_status(size):
    """base/small… 这个模型: 内置 / 已下载 / 需联网下载。"""
    from paths import bundle_dir
    if os.path.isdir(os.path.join(bundle_dir(), "models", f"faster-whisper-{size}")):
        return "内置"
    cache = os.path.expanduser(
        f"~/.cache/huggingface/hub/models--Systran--faster-whisper-{size}")
    return "已下载" if os.path.isdir(cache) else "需联网下载"


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
        self.root.title("音频与识别设置 — 骑砍语音指挥")
        self.root.configure(bg=BG)
        self.root.attributes("-topmost", True)

        tk.Label(
            self.root, text="⚙ 音频与识别设置",
            fg=GOLD, bg=BG, font=("Microsoft YaHei", 14, "bold"),
        ).pack(padx=24, pady=(16, 8))

        self._build_engine_section()

        tk.Label(
            self.root, text="🎙 麦克风：对着说话，看哪根音量条在跳，选中它，点保存",
            fg=GOLD, bg=BG, font=("Microsoft YaHei", 12, "bold"),
        ).pack(padx=24, pady=(4, 2))
        tk.Label(
            self.root, text="绿色条 = 有声音进来。选中后建议再说几句确认就是这一路。",
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
        self._add_row(frame, 0, None, "系统默认设备", saved is None)
        for row, (idx, name) in enumerate(self.devices, start=1):
            self._add_row(frame, row, idx, name, saved == name)
            self.meters[idx] = Meter(idx)

        self.status = tk.Label(self.root, text="", fg=GREEN, bg=BG,
                               font=("Microsoft YaHei", 11))
        self.status.pack(pady=(8, 0))

        btns = tk.Frame(self.root, bg=BG)
        btns.pack(pady=(6, 18))
        tk.Button(
            btns, text="💾 保存并使用这一路", command=self.save,
            font=("Microsoft YaHei", 12, "bold"), bg=GOLD, fg="#101418",
            activebackground="#e8c95a", relief="flat", padx=18, pady=6,
        ).pack(side="left", padx=8)
        tk.Button(
            btns, text="关闭", command=self.close,
            font=("Microsoft YaHei", 12), bg="#2a323a", fg=FG,
            activebackground="#3a444e", relief="flat", padx=18, pady=6,
        ).pack(side="left", padx=8)

        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(80, self._tick)

    def _build_engine_section(self):
        eng = tk.Frame(self.root, bg="#161c22", highlightthickness=1,
                       highlightbackground="#2a323a")
        eng.pack(padx=24, pady=(0, 8), fill="x")

        tk.Label(eng, text="🧠 识别引擎", fg=GOLD, bg="#161c22",
                 font=("Microsoft YaHei", 12, "bold")).grid(
            row=0, column=0, columnspan=4, sticky="w", padx=12, pady=(10, 2))

        gpu_ok, hw = detect_gpu()
        tk.Label(eng, text=hw, fg=(GREEN if gpu_ok else DIM), bg="#161c22",
                 font=("Microsoft YaHei", 9)).grid(
            row=1, column=0, columnspan=4, sticky="w", padx=12, pady=(0, 6))

        cur_model, cur_device = current_stt()

        tk.Label(eng, text="模型:", fg=FG, bg="#161c22",
                 font=("Microsoft YaHei", 10)).grid(
            row=2, column=0, sticky="e", padx=(12, 4), pady=(0, 10))
        self.model_map = {}
        mvals = []
        for val, disp, hint in MODEL_OPTS:
            tag = disp if val == "auto" else f"{disp} · {model_status(val)}"
            label = f"{tag}   — {hint}"
            self.model_map[label] = val
            mvals.append(label)
        self.model_box = ttk.Combobox(eng, state="readonly", values=mvals,
                                      font=("Microsoft YaHei", 10), width=34)
        self.model_box.grid(row=2, column=1, sticky="w", pady=(0, 10))
        self.model_box.set(next((lb for lb, v in self.model_map.items()
                                 if v == cur_model), mvals[0]))

        tk.Label(eng, text="运行:", fg=FG, bg="#161c22",
                 font=("Microsoft YaHei", 10)).grid(
            row=2, column=2, sticky="e", padx=(16, 4), pady=(0, 10))
        self.device_map = {disp: val for val, disp in DEVICE_OPTS}
        self.device_box = ttk.Combobox(
            eng, state="readonly", values=[d for _, d in DEVICE_OPTS],
            font=("Microsoft YaHei", 10), width=13)
        self.device_box.grid(row=2, column=3, sticky="w", padx=(0, 12), pady=(0, 10))
        self.device_box.set(next((d for d, v in self.device_map.items()
                                  if v == cur_device), DEVICE_OPTS[0][1]))

        tk.Label(eng,
                 text="改了模型 / 运行方式后，重启语音指挥生效。"
                      "「需联网下载」的模型第一次用要能连上网。",
                 fg=DIM, bg="#161c22", font=("Microsoft YaHei", 9),
                 wraplength=600, justify="left", anchor="w").grid(
            row=3, column=0, columnspan=4, sticky="w", padx=12, pady=(0, 10))

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
            self.status.config(text="先选一个麦克风设备再保存", fg="#ff8a8a")
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
        except Exception as e:
            self.status.config(text=f"保存失败: {e}", fg="#ff8a8a")
            return
        shown = "系统默认" if name is None else name
        self.status.config(
            text=f"✓ 已保存 · 麦克风:{shown} · 模型:{mv} · 运行:{dv}   "
                 f"(重启语音指挥后生效)", fg=GREEN)

    def close(self):
        for m in self.meters.values():
            m.close()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    SetupWindow().run()
