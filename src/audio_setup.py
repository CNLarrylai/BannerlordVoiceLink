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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS = os.path.join(ROOT, "config", "settings.yaml")

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
        self.root.title("音频输入设置 — 骑砍语音指挥")
        self.root.configure(bg=BG)
        self.root.attributes("-topmost", True)

        tk.Label(
            self.root, text="🎙 对着你的麦克风说话，看哪根音量条在跳，选中它，点保存",
            fg=GOLD, bg=BG, font=("Microsoft YaHei", 13, "bold"),
        ).pack(padx=24, pady=(18, 4))
        tk.Label(
            self.root, text="绿色条 = 有声音进来。选中后建议再说几句确认就是这一路。",
            fg=DIM, bg=BG, font=("Microsoft YaHei", 10),
        ).pack(padx=24, pady=(0, 12))

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
            self.status.config(text="先选一个设备再保存", fg="#ff8a8a")
            return
        name = None if sel == "__default__" else sel
        save_device(name)
        shown = "系统默认设备" if name is None else name
        self.status.config(
            text=f"✓ 已保存: {shown}   (重启语音指挥后生效)", fg=GREEN
        )

    def close(self):
        for m in self.meters.values():
            m.close()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    SetupWindow().run()
