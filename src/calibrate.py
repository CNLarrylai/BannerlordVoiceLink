# -*- coding: utf-8 -*-
"""校准模式 —— 新玩家上手教学 + 发音适配, 一举两得。

流程: 屏幕出题("请念: 冲锋") -> 你念 -> 实时判定 ✓/✗ -> 全部完成出报告:
  - 每条指令你的机器/嗓音/口音下的命中情况 + 平均延迟
  - "稳定错听"建议: 你念 X 总被听成 Y 且 Y 不撞别的指令 -> 一键学进个人词典
    (user_aliases.yaml, 软件更新不覆盖 —— 这就是"用你的发音优化你的本地体验";
     真·微调模型在玩家机器上不现实, 词典适配层是同效且零风险的做法)
  - 录音留档在 %LOCALAPPDATA%\\BannerlordVoice\\calibration\\ (仅本地,
    将来可自愿发给作者聚合改进全局模型)

单独跑: python src/app.py --mode calibrate
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
from rapidfuzz import fuzz  # noqa: E402

import dictionary  # noqa: E402
from i18n import t  # noqa: E402
from matcher import Matcher  # noqa: E402
from paths import config_path, log_dir  # noqa: E402

BG = "#101418"
FG = "#e8edf2"
DIM = "#9aa4ad"
GOLD = "#d4af37"
GREEN = "#7dff9b"
RED = "#ff8a8a"
BLUE = "#7Fd1ff"

# 内置兜底练习单: (group_key, order_key)。正常情况用 config/calibration.yaml。
DRILL = [
    ("infantry", None), ("archers", None), ("cavalry", None),
    ("horse_archers", None), ("all", None),
    (None, "charge"), (None, "halt"), (None, "advance"),
    (None, "fall_back"), (None, "retreat"), (None, "shield_wall"),
    (None, "line"), (None, "loose"), (None, "fire_at_will"),
    (None, "hold_fire"), (None, "mount_toggle"),
    ("all", "charge"), ("cavalry", "charge"),
]


def load_drill(commands, lang):
    """题目来源三级: ①usage.csv 攒够数据 -> 你的真实 top_n
    ②config/calibration.yaml 默认题库 ③内置 DRILL。返回 (清单, 来源说明key)。"""
    cfg = {}
    try:
        with open(config_path("calibration.yaml"), encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    except Exception:
        pass
    import usage
    top = usage.top_commands(lang, n=cfg.get("top_n", 20),
                             min_rows=cfg.get("min_usage_rows", 40))
    if top:
        drill = []
        for (g, o), _cnt in top:
            if g and g not in commands["groups"]:
                continue
            if o and o not in commands["orders"]:
                continue
            drill.append((g, o))
        if drill:
            return drill, "usage"
    conf = cfg.get("drill")
    if conf:
        drill = [(d.get("group"), d.get("order")) for d in conf
                 if (d.get("group") in commands["groups"] or not d.get("group"))
                 and (d.get("order") in commands["orders"] or not d.get("order"))]
        if drill:
            return drill, "default"
    return list(DRILL), "builtin"


def primary(commands, sec, key, lang):
    d = commands[sec][key]
    al = (d.get("en") if lang == "en" else d.get("aliases")) or ["?"]
    return al[0]


def build_items(commands, lang, drill=None):
    """练习单 -> [{say, group, order, combo}]。"""
    items = []
    joiner = " " if lang == "en" else ""
    for g, o in (drill if drill is not None else DRILL):
        parts = []
        if g:
            parts.append(primary(commands, "groups", g, lang))
        if o:
            parts.append(primary(commands, "orders", o, lang))
        items.append({"say": joiner.join(parts), "group": g, "order": o,
                      "combo": bool(g and o)})
    return items


def judge(matcher, item, heard):
    """这一句念得算不算过。"""
    tr = matcher.explain(heard)
    g_ok = True
    if item["group"]:
        g = tr.get("group")
        g_ok = bool(g and g["pass"] and g["name"] == item["group"])
    o_ok = True
    if item["order"]:
        o = tr.get("order")
        o_ok = bool(o and o["pass"] and o["name"] == item["order"])
    return g_ok and o_ok


def suggest_aliases(attempts, matcher, lang):
    """从失败记录里挑"稳定错听"作为个人词典候选。

    规则(宁缺勿滥): 单词题 + 没匹配对 + 听到了内容 + 和目标词相似(中文按
    拼音比 —— 错听多是"音近字异") + 这个听法现在匹配不到任何指令(否则会撞)。
    """
    out, seen = [], set()
    for a in attempts:
        if a["ok"] or a["combo"] or not a["heard"]:
            continue
        alias = a["heard"].strip().strip("。.!！?？,，")
        if not alias or len(alias) > 12:
            continue
        # 相似门槛: 字面>=50 或 (中文)拼音>=70。拼音门槛更高是因为随机中文的
        # 拼音串也共享大量 a/i/n 字母, 50 会把环境噪音放进来。
        ok_sim = fuzz.partial_ratio(a["say"].lower(), alias.lower()) >= 50
        if not ok_sim and lang != "en":
            from matcher import alias_pinyin
            py_a, py_b = alias_pinyin(a["say"]), alias_pinyin(alias)
            ok_sim = bool(py_a and py_b
                          and fuzz.partial_ratio(py_a, py_b) >= 70)
        if not ok_sim:
            continue          # 和目标差太远, 多半是环境噪音, 学了反而误触
        if matcher.parse(alias):
            continue          # 已能匹配到(别的)指令 -> 加了会撞, 跳过
        sec = "orders" if a["order"] else "groups"
        key = a["order"] or a["group"]
        sig = (sec, key, alias)
        if sig in seen:
            continue
        seen.add(sig)
        out.append({"section": sec, "key": key, "alias": alias,
                    "say": a["say"], "lang": lang})
    return out


class CalibrateGUI:
    def __init__(self):
        with open(config_path("settings.yaml"), encoding="utf-8") as f:
            self.cfg = yaml.safe_load(f)
        self.lang = self.cfg["stt"].get("language", "zh")
        self.commands = dictionary.load_commands()
        self.matcher = Matcher.from_config(self.commands, self.cfg["control"],
                                           lang=self.lang)
        drill, self.drill_source = load_drill(self.commands, self.lang)
        self.items = build_items(self.commands, self.lang, drill)
        self.attempts = []
        self.rec_dir = os.path.join(os.path.dirname(log_dir()), "calibration")
        self.q = queue.Queue()
        self.running = False
        self.listener = None

        self.root = tk.Tk()
        self.root.title(t("上手校准 — 骑砍语音指挥"))
        self.root.configure(bg=BG)
        self.root.geometry("640x520")
        self.root.minsize(520, 420)

        tk.Label(self.root, text=t("🎯 上手校准（教学 + 发音适配）"), fg=GOLD,
                 bg=BG, font=("Microsoft YaHei", 14, "bold")).pack(
            padx=18, pady=(14, 2))
        tk.Label(self.root,
                 text=t("跟着屏幕念指令, 系统实时判定。全部念完会生成报告, "
                        "并把「你的稳定错听」学进个人词典 —— 越用越懂你。"),
                 fg=DIM, bg=BG, font=("Microsoft YaHei", 9),
                 wraplength=580, justify="left").pack(padx=18, pady=(0, 10))

        # —— 布局规则: 按钮区先用 side="bottom" 打包 —— Tk 空间不够时牺牲的是
        #    后打包的控件, 按钮绝不能被挤出窗口(踩过: 高DPI矮窗口按钮消失)。
        btns = tk.Frame(self.root, bg=BG)
        btns.pack(side="bottom", pady=(6, 14))
        self.start_btn = tk.Button(btns, text=t("▶ 开始校准 (约3分钟)"),
                                   command=self.start,
                                   font=("Microsoft YaHei", 12, "bold"), bg=GOLD,
                                   fg="#101418", relief="flat", padx=20, pady=6)
        self.start_btn.pack(side="left", padx=6)
        self.skip_btn = tk.Button(btns, text=t("跳过这条"), command=self.skip,
                                  font=("Microsoft YaHei", 11), bg="#2a323a",
                                  fg=FG, relief="flat", padx=14, pady=6,
                                  state="disabled")
        self.skip_btn.pack(side="left", padx=6)

        # 大字出题区
        self.prompt = tk.Label(self.root, text=t("点「开始」后跟着念"), fg=BLUE,
                               bg="#161c22", font=("Microsoft YaHei", 24, "bold"),
                               pady=16)
        self.prompt.pack(fill="x", padx=18)
        self.progress = tk.Label(self.root, text="", fg=DIM, bg=BG,
                                 font=("Microsoft YaHei", 10))
        self.progress.pack(pady=(4, 0))
        self.verdict = tk.Label(self.root, text="", fg=DIM, bg=BG,
                                font=("Microsoft YaHei", 12))
        self.verdict.pack(pady=(2, 6))

        wrap = tk.Frame(self.root, bg=BG)
        wrap.pack(fill="both", expand=True, padx=18, pady=(0, 4))
        self.log = tk.Text(wrap, bg="#161c22", fg=FG, relief="flat", wrap="word",
                           font=("Microsoft YaHei", 10), state="disabled",
                           height=6, highlightthickness=0)
        vsb = tk.Scrollbar(wrap, command=self.log.yview)
        self.log.configure(yscrollcommand=vsb.set)
        self.log.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for tag, color in (("ok", GREEN), ("bad", RED), ("dim", DIM),
                           ("gold", GOLD)):
            self.log.tag_configure(tag, foreground=color)

        # 点开始前就把全流程讲清楚
        src_txt = {"usage": t("题目来源: 你的使用记录 Top{n} (最常用优先)"),
                   "default": t("题目来源: 默认题库 (使用数据攒够后自动改用你的常用指令)"),
                   "builtin": t("题目来源: 内置题库")}[self.drill_source]
        self._append(src_txt.format(n=len(self.items)) + "\n", "gold")
        self._append(t("流程一共 4 步:") + "\n", "gold")
        self._append(t("  ① 点「开始校准」(首次会加载识别模型, 稍等)") + "\n", "dim")
        self._append(t("  ② 屏幕大字出题, 共 {n} 条 —— 对着麦克风念出来即可; "
                       "没念对自动给第二次机会, 也可点「跳过这条」")
                     .format(n=len(self.items)) + "\n", "dim")
        self._append(t("  ③ 全部念完自动出报告: 命中率 + 平均识别速度") + "\n", "dim")
        self._append(t("  ④ 若发现「你的稳定错听」, 一键学进个人词典, "
                       "以后就按你的念法识别") + "\n", "dim")

        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(80, self._poll)

    # ---------- 流程控制 ----------

    def start(self):
        if self.running:
            return
        self.running = True
        self.start_btn.config(state="disabled")
        self.skip_btn.config(state="normal")
        self.attempts = []
        self._skip_flag = False
        threading.Thread(target=self._worker, daemon=True).start()

    def skip(self):
        self._skip_flag = True

    def _push(self, kind, *args):
        self.q.put((kind, args))

    def _worker(self):
        try:
            os.makedirs(self.rec_dir, exist_ok=True)
            self._push("status", t("加载识别模型中…"), GOLD)
            from stt import Transcriber
            tr = Transcriber(self.cfg)
            import soundfile as sf
            from audio import ContinuousListener
            self.listener = ContinuousListener(self.cfg)
            seg_iter = self.listener.segments()

            for idx, item in enumerate(self.items, 1):
                self._push("item", idx, len(self.items), item)
                self._skip_flag = False
                got = False
                for attempt in (1, 2):          # 每条最多两次机会
                    audio = None
                    for seg in seg_iter:        # 等一段语音(跳过键可打断)
                        if self._skip_flag or not self.running:
                            break
                        audio = seg
                        break
                    if self._skip_flag or not self.running or audio is None:
                        break
                    t0 = time.perf_counter()
                    heard = tr.transcribe(audio)
                    dt = time.perf_counter() - t0
                    stamp = time.strftime("%H%M%S")
                    try:
                        sf.write(os.path.join(
                            self.rec_dir,
                            f"{stamp}_{item['group'] or ''}{item['order'] or ''}"
                            f"_{attempt}.wav"), audio, 16000)
                    except Exception:
                        pass
                    ok = bool(heard) and judge(self.matcher, item, heard)
                    self.attempts.append({**item, "heard": heard, "ok": ok,
                                          "sec": dt})
                    self._push("verdict", ok, heard, dt, attempt)
                    if ok:
                        got = True
                        break
                if not self.running:
                    return
                if not got and self._skip_flag:
                    self.attempts.append({**item, "heard": "", "ok": False,
                                          "sec": 0.0})
                time.sleep(0.6)
            self._push("report")
        except Exception as e:
            self._push("status", t("校准出错: {e}").format(e=e), RED)

    # ---------- UI 更新 ----------

    def _poll(self):
        try:
            while True:
                kind, args = self.q.get_nowait()
                if kind == "status":
                    self.verdict.config(text=args[0], fg=args[1])
                elif kind == "item":
                    idx, total, item = args
                    self.prompt.config(text=t("请念：「{s}」").format(
                        s=item["say"]), fg=BLUE)
                    self.progress.config(
                        text=t("第 {i} / {n} 条").format(i=idx, n=total))
                    self.verdict.config(text=t("👂 听你说…"), fg=DIM)
                elif kind == "verdict":
                    ok, heard, dt, attempt = args
                    if ok:
                        self.verdict.config(text=t("✓ 很好！({s}s)").format(
                            s=f"{dt:.1f}"), fg=GREEN)
                        self._append(f"✓ {self.prompt.cget('text')}"
                                     f"  ← 「{heard}」\n", "ok")
                    else:
                        more = t(" · 再念一次试试") if attempt == 1 else ""
                        self.verdict.config(
                            text=t("✗ 听到「{h}」没对上{more}").format(
                                h=heard or "…", more=more), fg=RED)
                        if attempt == 2:
                            self._append(f"✗ {self.prompt.cget('text')}"
                                         f"  ← 「{heard}」\n", "bad")
                elif kind == "report":
                    self._show_report()
        except queue.Empty:
            pass
        if self.running or True:
            self.root.after(80, self._poll)

    def _append(self, text, tag):
        self.log.config(state="normal")
        self.log.insert("end", text, tag)
        self.log.see("end")
        self.log.config(state="disabled")

    # ---------- 报告与学习 ----------

    def _show_report(self):
        self.running = False
        if self.listener:
            self.listener.stop()
        self.skip_btn.config(state="disabled")
        okc = sum(1 for a in self.attempts if a["ok"])
        per_item_ok = {}
        for a in self.attempts:
            key = (a["group"], a["order"])
            per_item_ok[key] = per_item_ok.get(key, False) or a["ok"]
        rate = sum(per_item_ok.values()) / max(1, len(per_item_ok))
        lat = [a["sec"] for a in self.attempts if a["ok"]]
        avg = sum(lat) / max(1, len(lat))
        self.prompt.config(text=t("🎉 校准完成"), fg=GOLD)
        self.progress.config(text="")
        self.verdict.config(
            text=t("命中 {p}% · 平均识别 {s}s · 录音已存本地").format(
                p=f"{rate * 100:.0f}", s=f"{avg:.1f}"), fg=GREEN)
        self._append("\n" + t("—— 报告: {n} 条练习, 命中率 {p}% ——").format(
            n=len(per_item_ok), p=f"{rate * 100:.0f}") + "\n", "gold")

        self.sugs = suggest_aliases(self.attempts, self.matcher, self.lang)
        if self.sugs:
            self._append(t("发现你的稳定说法/错听, 建议学进个人词典:") + "\n",
                         "gold")
            for s in self.sugs:
                self._append(f"  「{s['say']}」→ 你的说法「{s['alias']}」\n",
                             "dim")
            self.start_btn.config(text=t("✍ 学进我的个人词典"),
                                  command=self.apply_sugs, state="normal")
            # 学不学是用户的选择 —— 必须给"不学"的路
            self.skip_btn.config(text=t("先不学"), state="normal",
                                 command=self._decline_sugs)
        else:
            self._reset_buttons()

    def apply_sugs(self):
        n = 0
        for s in self.sugs:
            if dictionary.add_user_alias(s["section"], s["key"], s["alias"],
                                         s["lang"]):
                n += 1
        self._append(t("✓ 已写入 {n} 条到个人词典 (语音程序按 F10 生效)")
                     .format(n=n) + "\n", "ok")
        self._reset_buttons()

    def _decline_sugs(self):
        self._append(t("· 本轮建议未采纳 (随时可再跑一轮)") + "\n", "dim")
        self._reset_buttons()

    def _reset_buttons(self):
        self.start_btn.config(text=t("▶ 再来一轮"), command=self.start,
                              state="normal")
        self.skip_btn.config(text=t("跳过这条"), command=self.skip,
                             state="disabled")

    def close(self):
        self.running = False
        if self.listener:
            self.listener.stop()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    CalibrateGUI().run()


if __name__ == "__main__":
    main()
