# -*- coding: utf-8 -*-
"""指令复盘 —— 逐条展示"听到什么 → 判定成什么 → 怎么执行的", 错配当场纠。

数据源: usage.csv (每条识别都落盘, 不依赖黑窗日志)。
纠错 = 选中记录 -> 指定正确的兵种/指令 -> 自动提取要学的说法 -> 学进
个人词典 user_aliases.yaml (软件更新不覆盖); 语音程序按 F10 立即生效。

游戏里呼出: 按 F11 (settings control.review_key); 启动器也有入口。
单独跑: python src/app.py --mode review
"""
import os
import sys
import tkinter as tk
from tkinter import ttk

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yaml  # noqa: E402

import dictionary  # noqa: E402
import usage  # noqa: E402
from i18n import t  # noqa: E402
from matcher import Matcher  # noqa: E402
from paths import config_path  # noqa: E402

BG = "#101418"
FG = "#e8edf2"
DIM = "#9aa4ad"
GOLD = "#d4af37"
GREEN = "#7dff9b"
RED = "#ff8a8a"

NONE_GROUP = "(不指定)"
NONE_ORDER = "(无)"


def _strip_alias(clean, alias):
    """从句子里剔掉一个已匹配别名 (字面剔; 字面不在句中用模糊对齐找区间剔)。"""
    from rapidfuzz import fuzz
    if not alias:
        return clean
    if alias in clean:
        return clean.replace(alias, "", 1)
    a = fuzz.partial_ratio_alignment(alias, clean)
    if a.score >= 65 and a.dest_end > a.dest_start:
        return clean[:a.dest_start] + clean[a.dest_end:]
    return clean


def suggest_alias(matcher, text, fix_part):
    """从整句提取"要学的说法": 剔掉其余已匹配部分, 只留要纠的那个词。

    例: 「全军出击」纠指令 -> 剔兵种"全军" -> 学"出击";
        「宜宾回来」纠兵种 -> 剔指令"回来"(命中别名是"退回来", 模糊对齐剔) -> 学"宜宾";
        「骑兵进攻弓箭首」纠目标 -> 剔兵种"骑兵"+指令"进攻" -> 学"弓箭首"。
    实在定位不到(如纯拼音命中)就整句保留, 交给用户手改。
    """
    clean = matcher._clean(text)
    tr = matcher.explain(text)
    for part in ("group", "order", "target"):
        if part == fix_part:
            continue
        d = tr.get(part)
        if not d:
            continue
        if part != "target" and not d.get("pass"):
            continue          # target 只有解析成功才会出现, 没有 pass 字段
        clean = _strip_alias(clean, d.get("alias") or "")
    return clean


class ReviewGUI:
    def __init__(self):
        with open(config_path("settings.yaml"), encoding="utf-8") as f:
            self.settings = yaml.safe_load(f)
        self.lang = self.settings["stt"].get("language", "zh")
        self.commands = dictionary.load_commands()
        self.matcher = Matcher.from_config(
            self.commands, self.settings["control"], lang=self.lang)
        # key<->显示名 (当前语言第一个别名)。纠错下拉只列"可纠成的基础兵种"
        # (步/弓/骑/骑射/全军, 即有编队选择键的) —— 左右半队/第N队那些是寻址
        # 伪兵种, 不是纠错目标, 排除(也避免它们的长英文名撑爆下拉宽度)。
        self.g_disp = {k: self._disp(d) for k, d in
                       self.commands["groups"].items()
                       if str(d.get("key", "")) != ""}
        # 纯模组指令(split, keys 空)同理不作为纠错目标
        self.o_disp = {k: self._disp(d) for k, d in
                       self.commands["orders"].items() if d.get("keys")}
        self.rows = []
        self._build()
        self.refresh()

    def _disp(self, data):
        al = data.get("en", []) if self.lang == "en" else data.get("aliases", [])
        return al[0] if al else "?"

    # ---------- UI ----------

    def _build(self):
        self.root = tk.Tk()
        self.root.title(t("指令复盘"))
        self.root.configure(bg=BG)
        self.root.geometry("860x640")
        self.root.attributes("-topmost", True)   # 游戏中呼出要压在前面

        tk.Label(self.root, text=t("📜 指令复盘 — 每句话都听成了什么、触发了什么"),
                 font=("Microsoft YaHei", 14, "bold"), fg=GOLD, bg=BG
                 ).pack(pady=(12, 2))
        tk.Label(self.root,
                 text=t("发现错配: 选中那条 → 指定正确指令/兵种 → 学进个人词典"),
                 font=("Microsoft YaHei", 9), fg=DIM, bg=BG).pack(pady=(0, 8))

        # 表格 (深色 ttk)
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("R.Treeview", background="#1a2026", fieldbackground="#1a2026",
                        foreground=FG, rowheight=26, font=("Microsoft YaHei", 10))
        style.configure("R.Treeview.Heading", background="#2a323a", foreground=FG,
                        font=("Microsoft YaHei", 10, "bold"))
        style.map("R.Treeview", background=[("selected", "#3a5a7a")])

        wrap = tk.Frame(self.root, bg=BG)
        wrap.pack(fill="both", expand=True, padx=14)
        cols = ("ts", "heard", "parsed", "via", "sec")
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings",
                                 style="R.Treeview", selectmode="browse")
        heads = {"ts": (t("时间"), 130), "heard": (t("听到"), 240),
                 "parsed": (t("判定"), 220), "via": (t("方式"), 120),
                 "sec": (t("耗时"), 60)}
        for c in cols:
            self.tree.heading(c, text=heads[c][0])
            self.tree.column(c, width=heads[c][1],
                             anchor="w" if c != "sec" else "e")
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.tag_configure("miss", foreground=RED)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        # 纠错面板
        fix = tk.Frame(self.root, bg=BG)
        fix.pack(fill="x", padx=14, pady=(8, 4))
        self.heard_lbl = tk.Label(fix, text=t("↑ 选中一条记录查看/纠错"),
                                  font=("Microsoft YaHei", 11, "bold"),
                                  fg=FG, bg=BG, anchor="w")
        self.heard_lbl.pack(fill="x")

        row2 = tk.Frame(fix, bg=BG)
        row2.pack(fill="x", pady=(6, 0))
        tk.Label(row2, text=t("正确兵种:"), fg=DIM, bg=BG,
                 font=("Microsoft YaHei", 10)).pack(side="left")
        self.g_var = tk.StringVar(value=t(NONE_GROUP))
        self.g_combo = ttk.Combobox(
            row2, textvariable=self.g_var, state="readonly", width=12,
            values=[t(NONE_GROUP)] + list(self.g_disp.values()))
        self.g_combo.pack(side="left", padx=(4, 16))
        tk.Label(row2, text=t("正确指令:"), fg=DIM, bg=BG,
                 font=("Microsoft YaHei", 10)).pack(side="left")
        self.o_var = tk.StringVar(value=t(NONE_ORDER))
        self.o_combo = ttk.Combobox(
            row2, textvariable=self.o_var, state="readonly", width=14,
            values=[t(NONE_ORDER)] + list(self.o_disp.values()))
        self.o_combo.pack(side="left", padx=(4, 16))
        # 指向性指令("骑兵进攻弓箭手")的第三维: 打击的敌方兵种
        tk.Label(row2, text=t("打击目标:"), fg=DIM, bg=BG,
                 font=("Microsoft YaHei", 10)).pack(side="left")
        self.t_var = tk.StringVar(value=t(NONE_GROUP))
        self.t_combo = ttk.Combobox(
            row2, textvariable=self.t_var, state="readonly", width=12,
            values=[t(NONE_GROUP)] + list(self.g_disp.values()))
        self.t_combo.pack(side="left", padx=(4, 0))
        self.g_combo.bind("<<ComboboxSelected>>", self._on_target_change)
        self.o_combo.bind("<<ComboboxSelected>>", self._on_target_change)
        self.t_combo.bind("<<ComboboxSelected>>", self._on_target_change)

        row3 = tk.Frame(fix, bg=BG)
        row3.pack(fill="x", pady=(6, 0))
        tk.Label(row3, text=t("要学的说法(自动提取, 可改):"), fg=DIM, bg=BG,
                 font=("Microsoft YaHei", 10)).pack(side="left")
        self.alias_var = tk.StringVar()
        tk.Entry(row3, textvariable=self.alias_var, width=22,
                 font=("Microsoft YaHei", 11), bg="#1a2026", fg=FG,
                 insertbackground=FG, relief="flat").pack(side="left", padx=6,
                                                          ipady=3)
        tk.Button(row3, text=t("✎ 保存绑定(学进个人词典)"), command=self.save_fix,
                  font=("Microsoft YaHei", 10, "bold"), bg=GOLD, fg="#101418",
                  activebackground="#e8c95a", relief="flat",
                  padx=12, pady=3).pack(side="left", padx=8)
        tk.Button(row3, text=t("🔄 刷新"), command=self.refresh,
                  font=("Microsoft YaHei", 10), bg="#2a323a", fg=FG,
                  activebackground="#3a444e", relief="flat",
                  padx=12, pady=3).pack(side="left")

        self.status = tk.Label(self.root,
                               text=t("绑定保存后: 语音程序按 F10 生效, 下次启动自动生效"),
                               font=("Microsoft YaHei", 9), fg=DIM, bg=BG)
        self.status.pack(pady=(4, 10))

    # ---------- 数据 ----------

    def refresh(self):
        self.rows = usage.recent(300)
        self.tree.delete(*self.tree.get_children())
        for i, r in enumerate(self.rows):
            ok = r["result"] == "ok"
            if ok:
                parts = []
                if r["group"]:
                    parts.append(self.g_disp.get(r["group"], r["group"]))
                if r["order"]:
                    parts.append(self.o_disp.get(r["order"], r["order"]))
                parsed = "✓ " + " · ".join(parts)
                if r.get("target"):
                    parsed += " → " + self.g_disp.get(r["target"], r["target"])
            else:
                parsed = t("✗ 未匹配")
            via = {"mod": t("模组"), "keys": t("按键")}.get(r["via"], "—")
            if r.get("engine"):
                via += f" [{r['engine']}]"
            self.tree.insert("", "end", iid=str(i), tags=() if ok else ("miss",),
                             values=(r["ts"][5:], r["heard"], parsed, via,
                                     r["stt_sec"]))
        if not self.rows:
            self.status.config(text=t("还没有记录: 先开语音指挥打一场"), fg=DIM)

    def _sel_row(self):
        sel = self.tree.selection()
        return self.rows[int(sel[0])] if sel else None

    def _on_select(self, _e=None):
        r = self._sel_row()
        if not r:
            return
        self.heard_lbl.config(text=t("听到: 「{t}」").format(t=r["heard"]))
        self.g_var.set(self.g_disp.get(r["group"], t(NONE_GROUP))
                       if r["group"] else t(NONE_GROUP))
        self.o_var.set(self.o_disp.get(r["order"], t(NONE_ORDER))
                       if r["order"] else t(NONE_ORDER))
        self.t_var.set(self.g_disp.get(r.get("target"), t(NONE_GROUP))
                       if r.get("target") else t(NONE_GROUP))
        self.alias_var.set("")
        self.status.config(
            text=t("把下面的兵种/指令改成这句话该触发的, 再点保存"), fg=DIM)

    def _key_of(self, disp, table):
        for k, v in table.items():
            if v == disp:
                return k
        return None

    def _changes(self, r):
        """(section, key, 建议说法) 列表: 用户选的与记录不同的那些部分。

        打击目标本质也是兵种词("骑兵进攻弓箭手"的"弓箭手"), 学进 groups ——
        matcher 的词序解析会按位置(动词后)自动把它当目标。
        """
        out = []
        gk = self._key_of(self.g_var.get(), self.g_disp)
        ok_ = self._key_of(self.o_var.get(), self.o_disp)
        tk_ = self._key_of(self.t_var.get(), self.g_disp)
        if ok_ and ok_ != (r["order"] or None):
            out.append(("orders", ok_,
                        suggest_alias(self.matcher, r["heard"], "order")))
        if gk and gk != (r["group"] or None):
            out.append(("groups", gk,
                        suggest_alias(self.matcher, r["heard"], "group")))
        if tk_ and tk_ != (r.get("target") or None):
            out.append(("groups", tk_,
                        suggest_alias(self.matcher, r["heard"], "target")))
        return out

    def _on_target_change(self, _e=None):
        r = self._sel_row()
        if not r:
            return
        ch = self._changes(r)
        # 单处改动: 建议说法回填输入框(可手改); 两处都改: 各自动提取, 输入框只作展示
        self.alias_var.set(ch[0][2] if len(ch) == 1 else
                           " / ".join(c[2] for c in ch))

    def save_fix(self):
        r = self._sel_row()
        if not r:
            self.status.config(text=t("先在表格里选中一条记录"), fg=RED)
            return
        ch = self._changes(r)
        if not ch:
            self.status.config(
                text=t("没有可保存的改动 (兵种/指令都与记录相同)"), fg=RED)
            return
        if len(ch) == 1 and self.alias_var.get().strip():
            ch = [(ch[0][0], ch[0][1],
                   self.matcher._clean(self.alias_var.get()))]
        done = []
        for section, key, alias in ch:
            if len(alias) < 2:
                self.status.config(
                    text=t("说法「{a}」太短(至少2个字), 请在输入框改").format(a=alias),
                    fg=RED)
                return
            disp = (self.g_disp if section == "groups" else self.o_disp)[key]
            dictionary.add_user_alias(section, key, alias)
            done.append((f'"{alias}" → {disp}' if self.lang == "en"
                         else f"「{alias}」→{disp}"))
        # 学完立刻用新词典重建 matcher, 复盘里的后续建议/判定同步新绑定
        self.commands = dictionary.load_commands()
        self.matcher = Matcher.from_config(
            self.commands, self.settings["control"], lang=self.lang)
        self.status.config(
            text=t("✓ 已学 {d} · 语音程序按 F10 生效(重启也生效)").format(
                d=" ".join(done)), fg=GREEN)

    def run(self):
        self.root.mainloop()


def main():
    ReviewGUI().run()


if __name__ == "__main__":
    main()
