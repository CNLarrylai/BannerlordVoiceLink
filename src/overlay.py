"""直播浮层 —— 置顶长条窗, 实时显示识别状态 (给观众看)。

形状是固定宽度的长条(overlay.width), 文本按像素截断加省略号 ——
窗口尺寸永远不变, 不会随文本长度跳变。
  上行: 实时状态 (👂 监听中… / 识别中… / ✓ 骑兵·冲锋 → …)
  下行: 上一句识别结果, 常驻不消失, 只被下一句替换 (overlay.debug_line 开关)

用线程安全队列接收 worker 线程的更新; Tkinter 必须跑在主线程。
"""
import queue
import tkinter as tk
import tkinter.font as tkfont

from i18n import t

BG = "#101418"


class Overlay:
    def __init__(self, cfg: dict):
        o = cfg.get("overlay", {})
        self.font_size = o.get("font_size", 22)
        self.show_debug = o.get("debug_line", True)
        self.width = o.get("width", 720)
        self.q = queue.Queue()
        self.root = None

    def push(self, status: str, detail: str = "", color: str = "#FFFFFF"):
        """更新上行实时状态 (worker 线程调用)。"""
        self.q.put(("status", (status, detail, color)))

    def push_debug(self, text: str):
        """更新下行常驻"上一句" (worker 线程调用)。"""
        self.q.put(("debug", text))

    # ---------- 内部 ----------

    def _fit(self, s: str, font, maxpx: int) -> str:
        """按像素宽度截断, 超出加省略号 —— 保证单行、窗口不变形。"""
        if font.measure(s) <= maxpx:
            return s
        while s and font.measure(s + "…") > maxpx:
            s = s[:-1]
        return s + "…"

    def _poll(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "status":
                    status, detail, color = payload
                    inner = self.width - 40
                    st = self._fit(status, self._f_status, int(inner * 0.62))
                    rest = inner - self._f_status.measure(st) - 16
                    self.status_lbl.config(text=st, fg=color)
                    self.detail_lbl.config(
                        text=self._fit(detail, self._f_detail, max(60, rest)))
                elif kind == "debug" and self.last_lbl is not None:
                    self.last_lbl.config(
                        text=self._fit(payload, self._f_last, self.width - 40))
        except queue.Empty:
            pass
        self.root.after(60, self._poll)

    def run(self):
        """阻塞运行 (主线程)。"""
        self.root = tk.Tk()
        self.root.title(t("骑砍语音指挥"))
        self.root.attributes("-topmost", True)
        self.root.configure(bg=BG)
        # 半透明, OBS 里可以用色键抠掉背景
        self.root.attributes("-alpha", 0.92)
        self.root.resizable(False, False)

        fs = self.font_size
        self._f_status = tkfont.Font(family="Microsoft YaHei", size=fs, weight="bold")
        self._f_detail = tkfont.Font(family="Microsoft YaHei", size=int(fs * 0.55))
        self._f_last = tkfont.Font(family="Microsoft YaHei", size=int(fs * 0.55))

        h1 = int(fs * 2.1)
        h2 = int(fs * 1.25) if self.show_debug else 0
        height = h1 + h2 + 18
        self.root.geometry(f"{self.width}x{height}+40+40")

        # 固定尺寸的容器: 内容再长也不会把窗口撑大
        body = tk.Frame(self.root, bg=BG, width=self.width, height=height)
        body.pack_propagate(False)
        body.pack(fill="both", expand=True)

        # 上行: 实时状态 + 补充说明 (同一行, 底部对齐)
        row1 = tk.Frame(body, bg=BG, width=self.width - 40, height=h1)
        row1.pack_propagate(False)
        row1.pack(fill="x", padx=20, pady=(8, 0))
        self.status_lbl = tk.Label(row1, text=t("待命中…"), fg="#7Fd1ff", bg=BG,
                                   font=self._f_status, anchor="w")
        self.status_lbl.pack(side="left", anchor="s")
        self.detail_lbl = tk.Label(row1, text=t("按住热键说话"), fg="#9aa4ad", bg=BG,
                                   font=self._f_detail, anchor="w")
        self.detail_lbl.pack(side="left", anchor="s", padx=(12, 0), pady=(0, 4))

        # 下行: 上一句识别结果 (常驻, 只被下一句替换)
        self.last_lbl = None
        if self.show_debug:
            tk.Frame(body, bg="#2a323a", height=1).pack(fill="x", padx=14, pady=(4, 0))
            row2 = tk.Frame(body, bg=BG, width=self.width - 40, height=h2)
            row2.pack_propagate(False)
            row2.pack(fill="x", padx=20)
            self.last_lbl = tk.Label(row2, text=t("上一条: (还没有)"), fg="#7a8494",
                                     bg=BG, font=self._f_last, anchor="w")
            self.last_lbl.pack(side="left", anchor="w", fill="x")

        self.root.after(60, self._poll)
        self.root.mainloop()
