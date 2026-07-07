# -*- coding: utf-8 -*-
"""游戏指令树 —— 可查验、可更正的"游戏里每个键意味着什么"。

代替原来只读的 docs/bannerlord-orders.md 指向:
  - 数据在 config/order_tree.yaml (玩家可改: 游戏改版/自改键位后在窗口里更正)
  - OrderTreeWindow: 树状查看 + 编辑 + 一键校验 commands.yaml 的键序
    是否都能在指令树里走通 (词典键位的对照物)。
"""
import re
import tkinter as tk
from tkinter import ttk

import yaml

from i18n import t
from paths import config_path

BG = "#101418"
FG = "#e8edf2"
DIM = "#9aa4ad"
GOLD = "#d4af37"
GREEN = "#7dff9b"
RED = "#ff8a8a"

KEY_RE = re.compile(r"^(f[1-9]|[0-9])$")

_HEADER = """\
# ============================================================
#  游戏指令树 —— 记录"游戏里每个键意味着什么" (词典键位的对照物)
# ============================================================
#  在「指令词典 → 🌲 游戏指令树」窗口里查看/更正/校验;
#  游戏改版或你改了游戏键位后, 在那里改这份表, 再点"校验词典"。
#  (此文件被窗口保存时重写, 注释只保留本头部)
# ============================================================
"""


def load_tree():
    with open(config_path("order_tree.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_tree(tree):
    with open(config_path("order_tree.yaml"), "w", encoding="utf-8") as f:
        f.write(_HEADER)
        yaml.safe_dump(tree, f, allow_unicode=True, sort_keys=False,
                       default_flow_style=False)


def _disp(node, lang):
    if not isinstance(node, dict):
        return str(node)
    if lang == "en":
        return node.get("en") or node.get("name", "?")
    return node.get("name", "?")


def resolve(tree, keys, lang="zh"):
    """一条键序在指令树里走一遍。返回 (ok, 说明)。"""
    menus = tree.get("menus") or {}
    direct = tree.get("direct") or {}
    if not keys:
        return False, t("空键序")
    k0 = str(keys[0]).lower()
    if len(keys) == 1:
        if k0 in direct:
            return True, _disp(direct[k0], lang)
        if k0 in menus:
            return False, t("{k} 只是打开菜单, 后面缺选项键").format(k=k0)
        return False, t("{k} 不在指令树里 (既非直接键也非菜单)").format(k=k0)
    if k0 not in menus:
        return False, t("{k} 不是菜单键, 不能接子选项").format(k=k0)
    menu = menus[k0]
    items = menu.get("items") or {}
    path = [_disp(menu, lang)]
    for k in keys[1:]:
        k = str(k).lower()
        if k not in items:
            return False, t("{menu} 菜单里没有 {k}").format(
                menu=_disp(menu, lang), k=k)
        path.append(_disp(items[k], lang))
    return True, " → ".join(path)


def validate_commands(tree, commands, lang="zh"):
    """校验 commands.yaml 全部键位。返回 [(名称, 键序串, ok, 说明)]。"""
    out = []
    groups = tree.get("groups") or {}
    for k, d in (commands.get("groups") or {}).items():
        al = (d.get("en") if lang == "en" else d.get("aliases")) or ["?"]
        gk = str(d.get("key", "")).lower()
        if gk in groups:
            out.append((al[0], gk, True, _disp(groups[gk], lang)))
        else:
            out.append((al[0], gk, False,
                        t("{k} 不在编队选择键里").format(k=gk)))
    for k, d in (commands.get("orders") or {}).items():
        al = (d.get("en") if lang == "en" else d.get("aliases")) or ["?"]
        keys = [str(x).lower() for x in (d.get("keys") or [])]
        ok, why = resolve(tree, keys, lang)
        out.append((al[0], "+".join(keys), ok, why))
    return out


class OrderTreeWindow:
    """指令树查看/编辑/校验窗口。master=None 时独立开 Tk (供审计)。"""

    def __init__(self, master=None, lang="zh"):
        self.lang = lang
        self.tree_data = load_tree()
        self.root = tk.Toplevel(master) if master is not None else tk.Tk()
        self.root.title(t("🌲 游戏指令树 — 查验与更正"))
        self.root.configure(bg=BG)
        self.root.geometry("760x640")
        self.root.minsize(620, 480)

        tk.Label(self.root,
                 text=t("🌲 游戏指令树：游戏里每个键的含义（词典键位以此校验）"),
                 fg=GOLD, bg=BG, font=("Microsoft YaHei", 13, "bold")).pack(
            padx=16, pady=(12, 2), anchor="w")
        tk.Label(self.root,
                 text=t("游戏改版/改过游戏键位时: 对照游戏内指令面板在这里更正, 再点「校验词典」。"),
                 fg=DIM, bg=BG, font=("Microsoft YaHei", 9)).pack(
            padx=16, pady=(0, 8), anchor="w")

        style = ttk.Style(self.root)
        style.theme_use("default")
        style.configure("Treeview", background="#161c22", fieldbackground="#161c22",
                        foreground=FG, font=("Microsoft YaHei", 10), rowheight=26)
        style.configure("Treeview.Heading", background="#1c2228", foreground=GOLD,
                        font=("Microsoft YaHei", 10, "bold"))

        wrap = tk.Frame(self.root, bg=BG)
        wrap.pack(fill="both", expand=True, padx=16)
        wrap.rowconfigure(0, weight=1)
        wrap.columnconfigure(0, weight=1)
        self.tv = ttk.Treeview(wrap, columns=("meaning",))
        self.tv.heading("#0", text=t("按键"))
        self.tv.heading("meaning", text=t("游戏内含义"))
        self.tv.column("#0", width=170, minwidth=120, stretch=False)
        self.tv.column("meaning", width=440, stretch=True)
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=vsb.set)
        self.tv.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        self.tv.bind("<<TreeviewSelect>>", self._on_select)

        # 编辑区
        ed = tk.Frame(self.root, bg=BG)
        ed.pack(fill="x", padx=16, pady=(8, 0))
        ed.columnconfigure(3, weight=1)
        tk.Label(ed, text=t("键:"), fg=FG, bg=BG,
                 font=("Microsoft YaHei", 10)).grid(row=0, column=0, padx=(0, 4))
        self.key_entry = tk.Entry(ed, width=6, font=("Consolas", 11),
                                  bg="#1c2228", fg=FG, insertbackground=FG,
                                  relief="flat")
        self.key_entry.grid(row=0, column=1, padx=(0, 10), ipady=3)
        tk.Label(ed, text=t("含义(中/英):"), fg=FG, bg=BG,
                 font=("Microsoft YaHei", 10)).grid(row=0, column=2, padx=(0, 4))
        self.name_entry = tk.Entry(ed, font=("Microsoft YaHei", 10), bg="#1c2228",
                                   fg=FG, insertbackground=FG, relief="flat")
        self.name_entry.grid(row=0, column=3, sticky="ew", ipady=3, padx=(0, 6))
        self.en_entry = tk.Entry(ed, font=("Microsoft YaHei", 10), bg="#1c2228",
                                 fg=FG, insertbackground=FG, relief="flat")
        self.en_entry.grid(row=0, column=4, sticky="ew", ipady=3)
        ed.columnconfigure(4, weight=1)

        btns = tk.Frame(self.root, bg=BG)
        btns.pack(fill="x", padx=16, pady=(6, 4))
        for txt, cmd, color in (
                (t("💾 保存修改"), self.save_edit, GOLD),
                (t("➕ 添加子项"), self.add_item, "#2a323a"),
                (t("🗑 删除所选"), self.delete_item, "#2a323a"),
                (t("🔍 校验词典"), self.validate, "#2a5a3a")):
            fg = "#101418" if color == GOLD else FG
            tk.Button(btns, text=txt, command=cmd, font=("Microsoft YaHei", 10,
                      "bold" if color == GOLD else "normal"),
                      bg=color, fg=fg, relief="flat", padx=12, pady=4).pack(
                side="left", padx=(0, 8))

        self.status = tk.Label(self.root, text=t("👆 选中一行可编辑; 改完即写入配置"),
                               fg=DIM, bg=BG, font=("Microsoft YaHei", 9),
                               anchor="w", justify="left")
        self.status.pack(fill="x", padx=16, pady=(2, 10))

        self._fill()

    # ---------- 树渲染 ----------

    def _fill(self):
        self.tv.delete(*self.tv.get_children())
        d = self.tree_data
        g = self.tv.insert("", "end", text=t("编队选择键"), open=True,
                           values=("",), tags=("sec",))
        self.tv.item(g, tags=())
        self._sec_ids = {"groups": g}
        for k, node in (d.get("groups") or {}).items():
            self.tv.insert(g, "end", iid=f"groups:{k}", text=k,
                           values=(_disp(node, self.lang),))
        for mk, menu in (d.get("menus") or {}).items():
            mid = self.tv.insert("", "end", iid=f"menu:{mk}", open=True,
                                 text=f"{mk}  ({t('菜单')})",
                                 values=(_disp(menu, self.lang),))
            for ik, node in (menu.get("items") or {}).items():
                self.tv.insert(mid, "end", iid=f"item:{mk}:{ik}",
                               text=f"{mk} + {ik}",
                               values=(_disp(node, self.lang),))
        dd = self.tv.insert("", "end", text=t("顶层直接键 (无子菜单)"), open=True,
                            values=("",))
        self._sec_ids["direct"] = dd
        for k, node in (d.get("direct") or {}).items():
            self.tv.insert(dd, "end", iid=f"direct:{k}", text=k,
                           values=(_disp(node, self.lang),))

    def _node_at(self, iid):
        """iid -> (容器dict, 键)。"""
        d = self.tree_data
        if iid.startswith("groups:"):
            return d["groups"], iid.split(":", 1)[1]
        if iid.startswith("direct:"):
            return d["direct"], iid.split(":", 1)[1]
        if iid.startswith("menu:"):
            return d["menus"], iid.split(":", 1)[1]
        if iid.startswith("item:"):
            _, mk, ik = iid.split(":")
            return d["menus"][mk]["items"], ik
        return None, None

    def _on_select(self, event=None):
        sel = self.tv.selection()
        for e in (self.key_entry, self.name_entry, self.en_entry):
            e.delete(0, "end")
        if not sel:
            return
        cont, k = self._node_at(sel[0])
        if cont is None:
            return
        node = cont.get(k)
        self.key_entry.insert(0, k)
        if isinstance(node, dict):
            self.name_entry.insert(0, node.get("name", ""))
            self.en_entry.insert(0, node.get("en", ""))

    # ---------- 编辑动作 ----------

    def _selected(self):
        sel = self.tv.selection()
        if not sel:
            self.status.config(text=t("先在上面选中一行"), fg=RED)
            return None
        return sel[0]

    def save_edit(self):
        iid = self._selected()
        if not iid:
            return
        cont, k = self._node_at(iid)
        if cont is None:
            self.status.config(text=t("这一行是分组标题, 不能编辑"), fg=RED)
            return
        nk = self.key_entry.get().strip().lower()
        if not KEY_RE.match(nk):
            self.status.config(text=t("键必须是 f1~f9 或数字 0~9"), fg=RED)
            return
        node = cont.get(k)
        if not isinstance(node, dict):
            node = {}
        node["name"] = self.name_entry.get().strip() or node.get("name", "")
        node["en"] = self.en_entry.get().strip() or node.get("en", "")
        if nk != k:
            if nk in cont:
                self.status.config(text=t("键 {k} 已存在").format(k=nk), fg=RED)
                return
            del cont[k]
        cont[nk] = node
        save_tree(self.tree_data)
        self._fill()
        self.status.config(text=t("✓ 已保存到 order_tree.yaml"), fg=GREEN)

    def add_item(self):
        iid = self._selected()
        if not iid:
            return
        # 加到: 选中菜单/菜单项 -> 该菜单; 选中编队/直接键 -> 对应容器
        if iid.startswith(("menu:", "item:")):
            mk = iid.split(":")[1]
            cont = self.tree_data["menus"][mk].setdefault("items", {})
        elif iid.startswith("groups:") or iid == self._sec_ids.get("groups"):
            cont = self.tree_data.setdefault("groups", {})
        else:
            cont = self.tree_data.setdefault("direct", {})
        nk = self.key_entry.get().strip().lower()
        if not KEY_RE.match(nk):
            self.status.config(text=t("先在「键」里填新按键 (f1~f9 或 0~9)"), fg=RED)
            return
        if nk in cont:
            self.status.config(text=t("键 {k} 已存在").format(k=nk), fg=RED)
            return
        cont[nk] = {"name": self.name_entry.get().strip() or "?",
                    "en": self.en_entry.get().strip() or "?"}
        save_tree(self.tree_data)
        self._fill()
        self.status.config(text=t("✓ 已添加并保存"), fg=GREEN)

    def delete_item(self):
        iid = self._selected()
        if not iid:
            return
        cont, k = self._node_at(iid)
        if cont is None or iid.startswith("menu:"):
            self.status.config(text=t("整个菜单/分组不允许删 (删它下面的具体键)"),
                               fg=RED)
            return
        del cont[k]
        save_tree(self.tree_data)
        self._fill()
        self.status.config(text=t("✓ 已删除并保存"), fg=GREEN)

    # ---------- 校验 ----------

    def validate(self):
        with open(config_path("commands.yaml"), encoding="utf-8") as f:
            commands = yaml.safe_load(f)
        rows = validate_commands(self.tree_data, commands, self.lang)
        bad = [r for r in rows if not r[2]]
        win = tk.Toplevel(self.root)
        win.title(t("校验结果 — 词典键位 vs 指令树"))
        win.configure(bg=BG)
        win.geometry("640x480")
        head = (t("❌ {n} 条键位走不通指令树, 请修正:").format(n=len(bad))
                if bad else t("✓ 词典全部 {n} 条键位都能在指令树里走通").format(
                    n=len(rows)))
        tk.Label(win, text=head, fg=(RED if bad else GREEN), bg=BG,
                 font=("Microsoft YaHei", 12, "bold")).pack(padx=14, pady=(12, 6),
                                                            anchor="w")
        txt = tk.Text(win, bg="#161c22", fg=FG, relief="flat", wrap="word",
                      font=("Microsoft YaHei", 10), state="normal")
        txt.pack(fill="both", expand=True, padx=14, pady=(0, 12))
        txt.tag_configure("ok", foreground=GREEN)
        txt.tag_configure("bad", foreground=RED)
        for name, seq, ok, why in sorted(rows, key=lambda r: r[2]):
            mark = "✓" if ok else "✗"
            txt.insert("end", f"{mark} {name}  [{seq}]  {why}\n",
                       "ok" if ok else "bad")
        txt.config(state="disabled")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    OrderTreeWindow().run()
