"""直播浮层 —— 一个置顶小窗, 实时显示识别到的指令 (给观众看)。

用线程安全队列接收 worker 线程的更新; Tkinter 必须跑在主线程。
"""
import queue
import tkinter as tk


class Overlay:
    def __init__(self, cfg: dict):
        self.font_size = cfg.get("overlay", {}).get("font_size", 22)
        self.q = queue.Queue()
        self.root = None

    def push(self, status: str, detail: str = "", color: str = "#FFFFFF"):
        """worker 线程调用: 更新显示内容。"""
        self.q.put((status, detail, color))

    def _poll(self):
        try:
            while True:
                status, detail, color = self.q.get_nowait()
                self.status_lbl.config(text=status, fg=color)
                self.detail_lbl.config(text=detail)
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
        self.detail_lbl.pack(padx=20, pady=(0, 14))

        self.root.after(60, self._poll)
        self.root.mainloop()
