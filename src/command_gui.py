"""指令词典 GUI —— 看词典、试说法、加别名。

三块功能:
  1. 左侧: 完整指令词典 (兵种/指令 -> 所有说法 -> 按键)
  2. 右上: 测试台 —— 输入任意一句话, 显示完整判定过程
     (命中了哪个别名、多少分、聊天过滤怎么判的、最终执不执行)
  3. 右下: 给某条指令添加新说法, 直接写进 commands.yaml
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

import yaml

from i18n import t
from matcher import CHAT_MARKERS, FILLERS, Matcher

from paths import bundle_dir, config_path  # noqa: E402

ROOT = bundle_dir()
SETTINGS = config_path("settings.yaml")
COMMANDS = config_path("commands.yaml")

BG = "#101418"
FG = "#e8edf2"
DIM = "#9aa4ad"
GOLD = "#d4af37"
GREEN = "#7dff9b"
RED = "#ff8a8a"
PURPLE = "#c9a0ff"


def load_all():
    import dictionary
    with open(SETTINGS, encoding="utf-8") as f:
        settings = yaml.safe_load(f)
    return settings, dictionary.load_commands()   # 基础词典+个人词典合并


def _edit_entry_line(section: str, key: str, line_re: str, replace_fn):
    """在 commands.yaml 里定位 section->key 条目下匹配 line_re 的行并改写。

    逐行扫描保留所有注释。成功返回 True。
    """
    with open(COMMANDS, encoding="utf-8") as f:
        lines = f.readlines()
    cur_top, cur_key = None, None
    for i, line in enumerate(lines):
        m = re.match(r"^(\w+):", line)
        if m:
            cur_top, cur_key = m.group(1), None
            continue
        m = re.match(r"^  (\w+):", line)
        if m:
            cur_key = m.group(1)
            continue
        if cur_top == section and cur_key == key:
            m = re.match(line_re, line)
            if m:
                lines[i] = replace_fn(m)
                with open(COMMANDS, "w", encoding="utf-8") as f:
                    f.writelines(lines)
                return True
    return False


def add_alias_to_yaml(section: str, key: str, alias: str, field: str = "aliases"):
    """把新别名追加到 commands.yaml 对应条目的 aliases/en 数组 (保留注释)。

    field: "aliases"(中文) 或 "en"(英文)。支持跨多行的数组: 定位到数组起始行
    后一直找到闭合的 ']' , 在其前插入 ', alias'。
    """
    with open(COMMANDS, encoding="utf-8") as f:
        lines = f.readlines()
    cur_top, cur_key, in_field = None, None, False
    field_re = re.compile(rf"^\s+{field}:\s*\[")
    for i, line in enumerate(lines):
        if re.match(r"^(\w+):", line):
            cur_top, cur_key, in_field = re.match(r"^(\w+):", line).group(1), None, False
            continue
        m = re.match(r"^  (\w+):", line)
        if m:
            cur_key, in_field = m.group(1), False
            continue
        if cur_top != section or cur_key != key:
            continue
        if not in_field and field_re.match(line):
            in_field = True
        if in_field and "]" in line:
            idx = line.rfind("]")
            lines[i] = line[:idx] + f", {alias}" + line[idx:]
            with open(COMMANDS, "w", encoding="utf-8") as f:
                f.writelines(lines)
            return True
    return False


# 允许的按键 (pydirectinput 键名): f1~f24 / 数字 / 字母 / 少量功能键
KEY_TOKEN_RE = re.compile(
    r"^(f([1-9]|1[0-9]|2[0-4])|[0-9a-z]|esc|escape|backspace|space|enter|tab)$"
)


def set_keys_in_yaml(section: str, key: str, keys: list):
    """改写指令的按键序列 (orders 的 keys: [...] 或 groups 的 key: "..")。"""
    if section == "orders":
        return _edit_entry_line(
            section, key, r"^(\s+keys:\s*\[).*?(\]\s*)$",
            lambda m: f"{m.group(1)}{', '.join(keys)}{m.group(2)}",
        )
    return _edit_entry_line(
        section, key, r'^(\s+key:\s*)\S.*?(\s*)$',
        lambda m: f'{m.group(1)}"{keys[0]}"\n',
    )


class CommandGUI:
    def __init__(self):
        self.settings, self.commands = load_all()
        self.lang = self.settings["stt"].get("language", "zh")
        self._build_matcher()

        self.root = tk.Tk()
        lang_tag = t("英文模式 English") if self.lang == "en" else t("中文模式")
        self.root.title(t("指令词典 [{mode}] — 骑砍语音指挥").format(mode=lang_tag))
        self.root.configure(bg=BG)
        self.root.geometry("1160x680")

        self.root.minsize(880, 560)
        style = ttk.Style(self.root)
        style.theme_use("default")
        style.configure("Treeview", background="#161c22", fieldbackground="#161c22",
                        foreground=FG, font=("Microsoft YaHei", 10), rowheight=26)
        style.configure("Treeview.Heading", background="#1c2228", foreground=GOLD,
                        font=("Microsoft YaHei", 10, "bold"))
        style.map("Treeview", background=[("selected", "#2a4a6a")])

        # 左右两栏, 中间分隔条可拖动伸缩
        paned = ttk.PanedWindow(self.root, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=14, pady=12)
        self.paned = paned

        # ========== 左: 词典树 + 完整说法 + 键位编辑 ==========
        left = tk.Frame(paned, bg=BG)
        paned.add(left, weight=3)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)
        left.bind("<Configure>", self._on_left_resize)

        _mode = t("🇬🇧 英文说法 English") if self.lang == "en" else t("🇨🇳 中文说法")
        tk.Label(left, text=t("📖 指令词典 · 当前显示 {mode}").format(mode=_mode),
                 fg=GOLD, bg=BG,
                 font=("Microsoft YaHei", 13, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 6))

        tree_wrap = tk.Frame(left, bg=BG)
        tree_wrap.grid(row=1, column=0, sticky="nsew")
        tree_wrap.rowconfigure(0, weight=1)
        tree_wrap.columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(tree_wrap, columns=("keys", "aliases"))
        self.tree.heading("#0", text=t("指令"))
        self.tree.heading("keys", text=t("按键"))
        self.tree.heading("aliases", text=t("可以说的话 (别名)"))
        self.tree.column("#0", width=150, minwidth=110, stretch=False)
        self.tree.column("keys", width=92, minwidth=70, stretch=False)
        self.tree.column("aliases", width=360, minwidth=180, stretch=True)
        vsb = ttk.Scrollbar(tree_wrap, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_wrap, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        self.item_map = {}
        self._fill_tree()
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        # 选中项的完整说法 (固定高度的只读框, 别名再长也不会挤压上面的树)
        self.detail = tk.Text(
            left, height=4, wrap="word", relief="flat", bg="#161c22", fg=DIM,
            font=("Microsoft YaHei", 10), padx=12, pady=8,
            highlightthickness=0, state="disabled", cursor="arrow")
        self.detail.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        self._set_detail(t("👆 选中一条, 这里显示它的全部说法"), DIM)

        # ---------- 键位编辑 ----------
        keyedit = tk.Frame(left, bg=BG)
        keyedit.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        keyedit.columnconfigure(1, weight=1)
        tk.Label(keyedit, text=t("✏ 改键位 (先在上面选一条):"), fg=GOLD, bg=BG,
                 font=("Microsoft YaHei", 11, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 4))
        self.keyedit_label = tk.Label(keyedit, text=t("未选中"), fg=DIM, bg=BG,
                                      font=("Microsoft YaHei", 10), width=15,
                                      anchor="w")
        self.keyedit_label.grid(row=1, column=0, padx=(0, 8))
        self.keys_entry = tk.Entry(keyedit, font=("Consolas", 12), bg="#1c2228",
                                   fg=FG, insertbackground=FG, relief="flat")
        self.keys_entry.grid(row=1, column=1, sticky="ew", ipady=5, padx=(0, 8))
        self.keys_entry.bind("<Return>", lambda e: self.save_keys())
        tk.Button(keyedit, text=t("保存键位"), command=self.save_keys,
                  font=("Microsoft YaHei", 11, "bold"), bg=GOLD, fg="#101418",
                  relief="flat", padx=14).grid(row=1, column=2)
        self.keyedit_hint = tk.Label(
            keyedit,
            text=t("格式: 空格分隔按键序列, 如「f1 f3」; 兵种填一个键如「2」。"
                   "必须与游戏指令菜单一致。"),
            fg=DIM, bg=BG, font=("Microsoft YaHei", 9), anchor="w",
            justify="left", wraplength=460)
        self.keyedit_hint.grid(row=2, column=0, columnspan=3, sticky="w", pady=(4, 0))
        tk.Button(keyedit, text=t("🌲 游戏指令树 (查验/更正键位含义)"),
                  command=self.open_tree, font=("Microsoft YaHei", 9),
                  bg="#2a323a", fg=FG, relief="flat", padx=10).grid(
            row=3, column=0, columnspan=3, sticky="w", pady=(6, 0))

        # ========== 右: 测试台 + 加别名 ==========
        right = tk.Frame(paned, bg=BG)
        paned.add(right, weight=2)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(2, weight=1)

        tk.Label(right, text=t("🧪 试一句 (看这句话会不会被执行、为什么)"),
                 fg=GOLD, bg=BG, font=("Microsoft YaHei", 13, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 6))

        entry_row = tk.Frame(right, bg=BG)
        entry_row.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        entry_row.columnconfigure(0, weight=1)
        self.test_entry = tk.Entry(entry_row, font=("Microsoft YaHei", 12),
                                   bg="#1c2228", fg=FG, insertbackground=FG,
                                   relief="flat")
        self.test_entry.grid(row=0, column=0, sticky="ew", ipady=6, padx=(0, 8))
        self.test_entry.bind("<Return>", lambda e: self.run_test())
        tk.Button(entry_row, text=t("测试"), command=self.run_test,
                  font=("Microsoft YaHei", 11, "bold"), bg=GOLD, fg="#101418",
                  relief="flat", padx=16).grid(row=0, column=1)

        self.out = tk.Text(right, bg="#161c22", fg=FG, relief="flat",
                           font=("Microsoft YaHei", 11), wrap="word",
                           state="disabled", height=12)
        self.out.grid(row=2, column=0, sticky="nsew")
        for tag, color in (("ok", GREEN), ("bad", RED), ("dim", DIM),
                           ("gold", GOLD), ("purple", PURPLE)):
            self.out.tag_configure(tag, foreground=color)

        # ---------- 右下: 加别名 ----------
        tk.Label(right, text=t("➕ 给指令加一种新说法 (立即写入词典)"),
                 fg=GOLD, bg=BG, font=("Microsoft YaHei", 12, "bold")).grid(
            row=3, column=0, sticky="w", pady=(12, 4))
        add_row = tk.Frame(right, bg=BG)
        add_row.grid(row=4, column=0, sticky="ew")
        add_row.columnconfigure(1, weight=1)

        self.target_map = {}
        values = []
        for k, d in self.commands.get("groups", {}).items():
            label = t("兵种: {name}").format(name=self._name(d))
            self.target_map[label] = ("groups", k)
            values.append(label)
        for k, d in self.commands.get("orders", {}).items():
            label = t("指令: {name}").format(name=self._name(d))
            self.target_map[label] = ("orders", k)
            values.append(label)
        self.target_box = ttk.Combobox(add_row, values=values, state="readonly",
                                       font=("Microsoft YaHei", 10), width=16)
        self.target_box.grid(row=0, column=0, padx=(0, 8))
        self.alias_entry = tk.Entry(add_row, font=("Microsoft YaHei", 11),
                                    bg="#1c2228", fg=FG, insertbackground=FG,
                                    relief="flat")
        self.alias_entry.grid(row=0, column=1, sticky="ew", ipady=5, padx=(0, 8))
        self.alias_entry.bind("<Return>", lambda e: self.add_alias())
        tk.Button(add_row, text=t("添加"), command=self.add_alias,
                  font=("Microsoft YaHei", 11, "bold"), bg=GOLD, fg="#101418",
                  relief="flat", padx=16).grid(row=0, column=2)

        self.status = tk.Label(right, text=t("提示: 在上面输入一句话, 看它会不会执行、为什么"),
                               fg=DIM, bg=BG, font=("Microsoft YaHei", 9))
        self.status.grid(row=5, column=0, sticky="w", pady=(6, 0))

        self.root.after(80, self._init_sash)
        print("聊天特征词 (句中出现即忽略):", "、".join(CHAT_MARKERS))
        print("填充词 (下令时可夹带, 不影响判定):", "、".join(FILLERS))

    def _build_matcher(self):
        self.matcher = Matcher.from_config(
            self.commands, self.settings["control"],
            lang=self.settings["stt"].get("language", "zh"))

    def _field(self):
        """当前语言对应的说法字段名 (英文模式=en, 否则=aliases)。"""
        return "en" if self.lang == "en" else "aliases"

    def _disp(self, d):
        """当前语言下这条指令的全部说法 (英文模式取 en, 空则回退中文)。"""
        if self.lang == "en":
            return d.get("en") or d.get("aliases", [])
        return d.get("aliases", [])

    def _name(self, d):
        al = self._disp(d)
        return al[0] if al else t("(无说法)")

    def _fill_tree(self):
        self.tree.delete(*self.tree.get_children())
        self.item_map = {}
        sep = ", " if self.lang == "en" else "、"
        gp = self.tree.insert("", "end", text=t("🛡 兵种 (编队)"), open=True)
        for k, d in self.commands.get("groups", {}).items():
            iid = self.tree.insert(gp, "end", text=self._name(d),
                                   values=(self._keydesc("groups", d),
                                           sep.join(self._disp(d))))
            self.item_map[iid] = ("groups", k)
        op = self.tree.insert("", "end", text=t("⚔ 指令 (动作)"), open=True)
        for k, d in self.commands.get("orders", {}).items():
            iid = self.tree.insert(op, "end", text=self._name(d),
                                   values=(self._keydesc("orders", d),
                                           sep.join(self._disp(d))))
            self.item_map[iid] = ("orders", k)

    def _keydesc(self, section, d):
        """键位列文本: 兵种 "按 2" / 指令 "f1+f3" / 无按键(走模组) "模组直达"。"""
        if section == "groups":
            k = str(d.get("key", "") or "")
            return t("按 {k}").format(k=k) if k else t("模组直达")
        keys = d.get("keys") or []
        return "+".join(keys) if keys else t("模组直达")

    def _set_detail(self, text, color=FG):
        self.detail.config(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert("1.0", text)
        self.detail.config(fg=color, state="disabled")

    def _init_sash(self):
        """把分隔条初始位置设到偏左宽一些, 让词典树默认就够宽显示别名。"""
        try:
            w = self.paned.winfo_width()
            if w > 100:
                self.paned.sashpos(0, int(w * 0.6))
        except Exception:
            pass

    def _on_left_resize(self, event):
        w = max(200, event.width - 30)
        if getattr(self, "keyedit_hint", None) is not None:
            self.keyedit_hint.config(wraplength=w)

    def _on_select(self, event=None):
        sel = self.tree.selection()
        self.keys_entry.delete(0, "end")
        if not sel or sel[0] not in self.item_map:
            self.keyedit_label.config(text=t("未选中"), fg=DIM)
            self._set_detail(t("👆 选中一条, 这里显示它的全部说法"), DIM)
            self._selected = None
            return
        section, k = self.item_map[sel[0]]
        self._selected = (section, k)
        d = self.commands[section][k]
        self.keyedit_label.config(text=self._name(d), fg=FG)
        cur = [d["key"]] if section == "groups" else d["keys"]
        self.keys_entry.insert(0, " ".join(cur))
        kind = t("兵种") if section == "groups" else t("指令")
        keydesc = self._keydesc(section, d)
        sep = ", " if self.lang == "en" else "、"
        self._set_detail(
            t("【{kind} · {name}】 键位 {keys}\n{say}：{phrases}").format(
                kind=kind, name=self._name(d), keys=keydesc,
                say=t("能说的话"), phrases=sep.join(self._disp(d))), FG)

    def save_keys(self):
        if not getattr(self, "_selected", None):
            self.status.config(text=t("先在左侧选中一条指令再改键位"), fg=RED)
            return
        section, k = self._selected
        tokens = [x.lower() for x in self.keys_entry.get().split()]
        if not tokens:
            self.status.config(text=t("键位不能为空"), fg=RED)
            return
        bad = [x for x in tokens if not KEY_TOKEN_RE.match(x)]
        if bad:
            self.status.config(
                text=t("无效按键: {bad} (如 f1 f3 或 0~9)").format(bad=" ".join(bad)),
                fg=RED)
            return
        if section == "groups" and len(tokens) != 1:
            self.status.config(text=t("兵种只填一个选中键 (如 2)"), fg=RED)
            return
        if not set_keys_in_yaml(section, k, tokens):
            self.status.config(text=t("写入失败: commands.yaml 里没找到该条目"), fg=RED)
            return
        name = self._name(self.commands[section][k])
        self.settings, self.commands = load_all()
        self._build_matcher()
        self._fill_tree()
        self.status.config(
            text=t("✓ 「{name}」键位已改为 {keys} (切回语音程序按 F10 热重载生效)")
            .format(name=name, keys=" ".join(tokens)),
            fg=GREEN)
        if self.test_entry.get().strip():
            self.run_test()

    def open_tree(self):
        from order_tree import OrderTreeWindow
        OrderTreeWindow(master=self.root, lang=self.lang)

    def _print(self, text, tag=None):
        self.out.insert("end", text + "\n", tag or ())

    def run_test(self):
        text = self.test_entry.get().strip()
        self.out.config(state="normal")
        self.out.delete("1.0", "end")
        if not text:
            self.out.config(state="disabled")
            return
        tr = self.matcher.explain(text)
        self._print(t("输入: 「{t}」").format(t=text), "gold")
        if tr["chat_marker"]:
            self._print(t("✗ 忽略 — {r}").format(r=tr["reason"]), "bad")
            self._print(t("  (想让它当指令? 这句话含聊天特征词, 换个说法或去掉该词)"),
                        "dim")
            self.out.config(state="disabled")
            return
        g, o = tr["group"], tr["order"]
        if g:
            mark, tag = ("✓", "ok") if g["pass"] else ("✗", "bad")
            self._print(t("{mark} 兵种: {name}  命中「{alias}」 {score}分").format(
                mark=mark, name=g["name"], alias=g["alias"], score=g["score"]), tag)
        else:
            self._print(t("— 没匹配到兵种 (会作用于当前选中编队)"), "dim")
        if o:
            mark, tag = ("✓", "ok") if o["pass"] else ("✗", "bad")
            self._print(t("{mark} 指令: {name}  命中「{alias}」 {score}分").format(
                mark=mark, name=o["name"], alias=o["alias"], score=o["score"]), tag)
        else:
            self._print(t("✗ 没匹配到任何指令动作"), "bad")
        if tr.get("target"):
            tg = tr["target"]
            self._print(
                t("◎ 打击目标: {name}  命中「{alias}」 {score}分"
                  "  (敌方编队, 游戏内需准星锁定它)").format(
                    name=tg["name"], alias=tg["alias"], score=tg["score"]), "purple")
        if tr["coverage"]:
            cov = tr["coverage"]
            tag = "bad" if cov["is_chat"] else "dim"
            self._print(t("聊天过滤: {why}").format(why=cov["why"]), tag)
        if tr["result"]:
            r = tr["result"]
            keys = []
            if r["group"]:
                keys.append("1 2 3 4" if r["group"]["select"] == "all"
                            else r["group"]["select"])
            keys += r["order"]["keys"]
            self._print("\n" + t("▶ 会执行!  发送按键: {keys}").format(
                keys="  ".join(keys)), "ok")
        else:
            self._print("\n" + t("✗ 不会执行 — {r}").format(r=tr["reason"]), "bad")
            self._print(t("  (应该被执行? 用下面「加说法」把关键词加进对应指令)"),
                        "dim")
        self.out.config(state="disabled")

    def add_alias(self):
        label = self.target_box.get()
        alias = self.alias_entry.get().strip().rstrip("!！。.?？")
        if self.lang == "en":
            alias = alias.lower()
        if not label or not alias:
            self.status.config(text=t("先选目标指令、再填新说法"), fg=RED)
            return
        # 查重 (只在当前语言的说法里查)
        for sec in ("groups", "orders"):
            for k, d in self.commands.get(sec, {}).items():
                if alias in self._disp(d):
                    self.status.config(
                        text=t("「{alias}」已存在于 {name}").format(
                            alias=alias, name=self._name(d)), fg=RED)
                    return
        section, key = self.target_map[label]
        # 写进个人词典(user_aliases.yaml): 软件版本更新会刷新 commands.yaml,
        # 但绝不会动个人词典 —— 用户加的说法永远保得住。
        import dictionary
        dictionary.add_user_alias(section, key, alias,
                                  "en" if self.lang == "en" else "zh")
        # 重新加载, 让词典/匹配器立即生效
        self.settings, self.commands = load_all()
        self._build_matcher()
        self._fill_tree()
        self.status.config(
            text=t("✓ 已把「{alias}」加进 {label} (切回语音程序按 F10 热重载生效)")
            .format(alias=alias, label=label),
            fg=GREEN)
        self.alias_entry.delete(0, "end")
        if self.test_entry.get().strip():
            self.run_test()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    CommandGUI().run()
