"""直播浮层 —— 一个置顶小窗, 实时显示识别到的指令 (给观众看)。

底部可选一行小字 debug: 上一条听到什么 → 匹配成哪条 → 发了什么键, 常驻不消失,
方便主播和粉丝实时排错 (打包版语音模式没有黑窗)。用 overlay.debug_line 开关。

用线程安全队列接收 worker 线程的更新; Tkinter 必须跑在主线程。
"""
import queue
import tkinter as tk


class Overlay:
    def __init__(self, cfg: dict):
        o = cfg.get("overlay", {})
        self.font_size = o.get("font_size", 22)
        self.show_debug = o.get("debug_line", True)
        self.q = queue.Queue()
        self.root = None

    def push(self, status: str, detail: str = "", color: str = "#FFFFFF"):
        """更新主状态行 (worker 线程调用)。"""
        self.q.put(("status", (status, detail, color)))

    def push_debug(self, text: str):
        """更新底部常驻 debug 行 (worker 线程调用)。"""
        self.q.put(("debug", text))

    def _poll(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "status":
                    status, detail, color = payload
                    self.status_lbl.config(text=status, fg=color)
                    self.detail_lbl.config(text=detail)
                elif kind == "debug" and self.debug_lbl is not None:
                    self.debug_lbl.config(text=payload)
        except queue.Empty:
            pass
        self.root.after(60, self._poll)

    def run(self):
        """阻塞运行 (主线程)。"""
        self.root = tk.Tk()
        self.root.title("骑砍语音指挥")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#101418")
        self.root.geometry("+40+40")
        # 半透明, OBS 里可以用色键抠掉背景
        self.root.attributes("-alpha", 0.92)

        self.status_lbl = tk.Label(
            self.root, text="待命中…", fg="#7Fd1ff", bg="#101418",
            font=("Microsoft YaHei", self.font_size, "bold"),
        )
        self.status_lbl.pack(padx=20, pady=(14, 4))

        self.detail_lbl = tk.Label(
            self.root, text="按住热键说话", fg="#9aa4ad", bg="#101418",
            font=("Microsoft YaHei", int(self.font_size * 0.7)),
        )
        self.detail_lbl.pack(padx=20, pady=(0, 10))

        self.debug_lbl = None
        if self.show_debug:
            tk.Frame(self.root, bg="#2a323a", height=1).pack(fill="x", padx=14)
            self.debug_lbl = tk.Label(
                self.root, text="上一条: (还没有)", fg="#7a8494", bg="#101418",
                font=("Microsoft YaHei", max(9, int(self.font_size * 0.42))),
                wraplength=max(280, self.font_size * 16), justify="left", anchor="w",
            )
            self.debug_lbl.pack(padx=16, pady=(6, 12), fill="x")

        self.root.after(60, self._poll)
        self.root.mainloop()
