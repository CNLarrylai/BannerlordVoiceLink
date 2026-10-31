"""测试模式 GUI —— 持续监听, 窗口里实时显示"听到什么、匹配成哪条指令"，
不发任何按键 (安全练习 / 调麦克风 / 验证说法)。

源码与打包都有可见窗口。单独跑: python src/app.py --mode listen
"""
import os
import queue
import sys
import threading
import time
import tkinter as tk

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yaml  # noqa: E402

from audio import ContinuousListener  # noqa: E402
from i18n import t as _t  # noqa: E402
from matcher import Matcher  # noqa: E402
from paths import config_path  # noqa: E402

BG = "#101418"
FG = "#e8edf2"
DIM = "#9aa4ad"
GOLD = "#d4af37"
GREEN = "#7dff9b"
RED = "#ff8a8a"
BLUE = "#7Fd1ff"


class ListenGUI:
    def __init__(self):
        import dictionary
        with open(config_path("settings.yaml"), encoding="utf-8") as f:
            self.cfg = yaml.safe_load(f)
        self.commands = dictionary.load_commands()   # 含个人词典
        self.lang = self.cfg["stt"].get("language", "zh")
        self.matcher = Matcher.from_config(self.commands, self.cfg["control"],
                                           lang=self.lang)
        self.prefixes = self.cfg["control"].get("command_prefix") or []
        self.sr = self.cfg["audio"]["samplerate"]
        self.q = queue.Queue()
        self.running = True
        self.listener = None

        self.root = tk.Tk()
        self.root.title(_t("测试模式 · 只听不发键 — 骑砍语音指挥"))
        self.root.configure(bg=BG)
        self.root.geometry("560x480")
        self.root.minsize(420, 320)

        tk.Label(self.root, text=_t("🎧 测试模式（只听不发键）"), fg=GOLD, bg=BG,
                 font=("Microsoft YaHei", 14, "bold")).pack(padx=18, pady=(14, 2))
        tk.Label(self.root,
                 text=_t("对着麦克风说指令，下面实时显示识别结果。不会往游戏发按键，随便练。"),
                 fg=DIM, bg=BG, font=("Microsoft YaHei", 9),
                 wraplength=520, justify="left").pack(padx=18, pady=(0, 8))

        self.status = tk.Label(self.root, text=_t("启动中…"), fg=BLUE, bg=BG,
                               font=("Microsoft YaHei", 12, "bold"))
        self.status.pack(padx=18, pady=(0, 8))

        wrap = tk.Frame(self.root, bg=BG)
        wrap.pack(fill="both", expand=True, padx=18, pady=(0, 14))
        self.log = tk.Text(wrap, bg="#161c22", fg=FG, relief="flat", wrap="word",
                           font=("Microsoft YaHei", 11), state="disabled",
                           highlightthickness=0)
        vsb = tk.Scrollbar(wrap, command=self.log.yview)
        self.log.configure(yscrollcommand=vsb.set)
        self.log.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for tag, color in (("ok", GREEN), ("bad", RED), ("dim", DIM), ("gold", GOLD)):
            self.log.tag_configure(tag, foreground=color)

        self.root.protocol("WM_DELETE_WINDOW", self.close)
        threading.Thread(target=self._worker, daemon=True).start()
        self.root.after(80, self._poll)

    def _push(self, kind, *args):
        self.q.put((kind, args))

    def _worker(self):
        # 模型没下过就先下载(带进度), 再加载。都在线程里, 窗口先显示。
        import models
        # 有效模型必须和真实引擎算的一样(以前这里写死 auto->base, 引擎却用 small,
        # 于是测试模式白下一个用不上的模型); 内置进包的不再重复下载。
        from stt import model_available, resolve_stt_config
        eff = resolve_stt_config(self.cfg["stt"])[0]
        if not model_available(eff):
            self._push("status", _t("首次下载模型 {m}（{size}）…").format(
                m=eff, size=models.size_hint(eff)), GOLD)
            try:
                models.download(eff, lambda d, t: self._push("dl", (d, t)))
            except Exception as e:
                self._push("status", _t("模型下载失败: {e}").format(e=e), RED)
                return
        self._push("status", _t("加载识别模型中…"), GOLD)
        try:
            from stt import Transcriber
            tr = Transcriber(self.cfg)
        except Exception as e:
            self._push("status", _t("模型加载失败: {e}").format(e=e), RED)
            return
        self._push("status", _t("👂 监听中…（说指令试试）"), BLUE)
        if self.prefixes:
            self._push("line", _t("已开口令前缀 {p}，要先说前缀。").format(
                p=self.prefixes), "dim")
        self.listener = ContinuousListener(self.cfg)
        try:
            for audio in self.listener.segments():
                if not self.running:
                    break
                t0 = time.perf_counter()
                text = tr.transcribe(audio)
                dt = time.perf_counter() - t0
                if not text:
                    continue
                cleaned = text
                if self.prefixes:
                    hit = next((p for p in self.prefixes if p in text), None)
                    if not hit:
                        self._push("item", "chat", text, _t("（无口令前缀，忽略）"), dt)
                        continue
                    cleaned = text.replace(hit, "", 1).strip()
                parsed = self.matcher.parse(cleaned)
                if not parsed:
                    self._push("item", "no", text, _t("未匹配 / 聊天，忽略"), dt)
                    continue
                g, o = parsed.get("group"), parsed.get("order")
                ak = "en" if self.lang == "en" else "aliases"
                desc = []
                if g:
                    desc.append(self.commands["groups"][g["name"]][ak][0])
                if o:
                    desc.append(self.commands["orders"][o["name"]][ak][0])
                keys = ([g["select"]] if g else []) + (o["keys"] if o else [])
                self._push("item", "ok", text,
                           f"{' · '.join(desc)}   "
                           + _t("→ 按键 {keys}").format(keys=" ".join(keys)), dt)
        except Exception as e:
            self._push("status", _t("麦克风/识别出错: {e}").format(e=e), RED)

    def _poll(self):
        try:
            while True:
                kind, args = self.q.get_nowait()
                if kind == "status":
                    self.status.config(text=args[0], fg=args[1])
                elif kind == "dl":
                    d, tot = args[0]
                    if tot:
                        self.status.config(
                            text=_t("⬇ 下载模型中… {pct}%  ({d}/{t} MB)").format(
                                pct=f"{min(100, d/tot*100):.0f}",
                                d=f"{d/1048576:.0f}", t=f"{tot/1048576:.0f}"),
                            fg=GOLD)
                    else:
                        self.status.config(
                            text=_t("⬇ 下载模型中… 已下 {d} MB").format(
                                d=f"{d/1048576:.0f}"), fg=GOLD)
                elif kind == "line":
                    self._append(args[0] + "\n", args[1])
                elif kind == "item":
                    verdict, heard, result, dt = args
                    ts = time.strftime("%H:%M:%S")
                    tag = {"ok": "ok", "no": "bad", "chat": "dim"}[verdict]
                    mark = {"ok": "✓", "no": "✗", "chat": "·"}[verdict]
                    self._append(f"[{ts}] {mark} {result}\n", tag)
                    self._append("        " + _t("听到:「{t}」  识别{s}s").format(
                        t=heard, s=f"{dt:.2f}") + "\n", "dim")
        except queue.Empty:
            pass
        if self.running:
            self.root.after(80, self._poll)

    def _append(self, text, tag):
        self.log.config(state="normal")
        self.log.insert("end", text, tag)
        self.log.see("end")
        self.log.config(state="disabled")

    def close(self):
        self.running = False
        if self.listener:
            self.listener.stop()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    ListenGUI().run()


if __name__ == "__main__":
    main()
