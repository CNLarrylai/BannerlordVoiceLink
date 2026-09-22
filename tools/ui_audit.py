# -*- coding: utf-8 -*-
"""UI 自动验收 —— 两种语言构建每个窗口, 检测文本截断 + 截图存档。

原理(本地化 UI 测试的标准做法):
  - 截断判据: 控件实际尺寸 < 其内容所需尺寸 (winfo_width < winfo_reqwidth)。
  - 每次 UI 改动后跑一遍: zh/en 各构建一次, 任何 Label/Button/Combobox
    被截断都会点名报错; 同时截图到 tests/results/ui/ 供人眼验收。

用法: python tools/ui_audit.py          # 全部窗口 x 两种语言
退出码非 0 = 有截断, 修完再跑。
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 注意: 不开 DPI 感知 —— 真实应用就是 DPI-unaware 模式跑的, 审计必须
# 在同一渲染模式下检测截断才和用户看到的一致。截图用缩放比换算 bbox。
import tkinter as tk  # noqa: E402
from tkinter import ttk  # noqa: E402

import i18n  # noqa: E402
from audio_setup import save_yaml_setting  # noqa: E402

SHOT_DIR = os.path.join(ROOT, "tests", "results", "ui")
# 有 Pillow 才截图 (截断检测不依赖它)
try:
    from PIL import ImageGrab
    _HAS_PIL = True
except Exception:
    _HAS_PIL = False

TEXTY = (tk.Label, tk.Button, tk.Radiobutton, tk.Checkbutton, ttk.Combobox)


def _walk(w):
    yield w
    for c in w.winfo_children():
        yield from _walk(c)


def find_clipped(root):
    """返回 [(控件类名, 文本, 实际尺寸, 需要尺寸)] —— 被截断的文本控件。"""
    root.update_idletasks()
    root.update()
    bad = []
    for w in _walk(root):
        if not isinstance(w, TEXTY):
            continue
        if not w.winfo_ismapped():
            continue   # grid_remove/pack_forget 隐藏中的控件, 不算截断
        try:
            text = w.cget("text") if not isinstance(w, ttk.Combobox) else w.get()
        except Exception:
            text = "?"
        if not str(text).strip():
            continue
        # Combobox 内部裁剪不反映在 reqwidth 上: 按字符单位比较设定宽 vs 内容宽
        if isinstance(w, ttk.Combobox):
            from i18n import text_units
            vals = list(w.cget("values") or [])
            if vals:
                need = max(text_units(str(v)) for v in vals)
                have = int(str(w.cget("width")) or 0)
                if have + 1 < need:
                    bad.append(("Combobox", str(vals[0])[:40],
                                f"宽{have}字符", f"内容最长{need}字符"))
            continue
        # wraplength 的 Label 换行是设计行为, reqwidth 已按换行后计算
        aw, ah = w.winfo_width(), w.winfo_height()
        rw, rh = w.winfo_reqwidth(), w.winfo_reqheight()
        if aw + 2 < rw or ah + 2 < rh:
            bad.append((type(w).__name__, str(text)[:40].replace("\n", "\\n"),
                        f"{aw}x{ah}", f"{rw}x{rh}"))
    return bad


def squeezed_buttons(root):
    """缩到窗口 minsize 后, 检查按钮是否被 pack 挤出可视区。

    教训(校准窗口): pack 空间不够时牺牲后打包的控件, 高DPI矮窗口下
    "开始"按钮直接消失。规则: 按钮必须 side=bottom 先打包。
    """
    try:
        minw, minh = root.minsize()
    except Exception:
        return []
    if minw <= 1 or minh <= 1:
        return []          # 没设 minsize 的窗口不做此检查
    old = root.geometry()
    root.geometry(f"{minw}x{minh}")
    root.update()
    bad = []
    ry2 = root.winfo_rooty() + root.winfo_height()
    for w in _walk(root):
        if not isinstance(w, tk.Button):
            continue
        label = str(w.cget("text"))[:20].replace("\n", "\\n")
        if not w.winfo_ismapped():
            bad.append(("Button", label, f"minsize {minw}x{minh}", "被挤出窗口"))
        elif w.winfo_rooty() + w.winfo_height() > ry2 + 2:
            bad.append(("Button", label, f"minsize {minw}x{minh}", "超出下边缘"))
    root.geometry(old)
    root.update()
    return bad


def _full_check(root):
    return find_clipped(root) + squeezed_buttons(root)


def shot(root, name):
    if not _HAS_PIL:
        return
    os.makedirs(SHOT_DIR, exist_ok=True)
    root.update_idletasks()
    root.lift()
    root.attributes("-topmost", True)
    root.update()
    time.sleep(0.3)
    # DPI-unaware 进程里 Tk 坐标是逻辑像素, 截屏是物理像素:
    # 用 物理屏宽/逻辑屏宽 求缩放比换算 bbox (免注册表、免DPI API)
    full = ImageGrab.grab()
    scale = full.width / root.winfo_screenwidth()
    x, y = root.winfo_rootx(), root.winfo_rooty()
    w, h = root.winfo_width(), root.winfo_height()
    box = (max(0, int((x - 8) * scale)), max(0, int((y - 34) * scale)),
           min(full.width, int((x + w + 8) * scale)),
           min(full.height, int((y + h + 8) * scale)))
    full.crop(box).save(os.path.join(SHOT_DIR, name + ".png"))


def audit(lang):
    i18n.set_lang(lang)
    fails = 0

    # --- 启动器 ---
    import launcher as L
    orig = L._read_language
    L._read_language = lambda: lang
    try:
        win = L.Launcher()
        bad = _full_check(win.root)
        shot(win.root, f"launcher_{lang}")
        # 首次 GPU 引导弹窗 (新用户第一眼看到的对话框, 构建无副作用: 只在点下载后才联网)
        from gpu_setup import GpuOfferDialog
        dlg = GpuOfferDialog(win.root)
        bad += _full_check(dlg.win)
        shot(dlg.win, f"gpu_offer_{lang}")
        dlg.win.destroy()
        win.root.destroy()
    finally:
        L._read_language = orig
    fails += _report("launcher", lang, bad)

    # --- 指令词典 ---
    from command_gui import CommandGUI
    g = CommandGUI()
    bad = _full_check(g.root)
    shot(g.root, f"command_gui_{lang}")
    g.root.destroy()
    fails += _report("command_gui", lang, bad)

    # --- 音频设置 (会开麦克风音量流, 构建后立即关) ---
    from audio_setup import SetupWindow
    w = SetupWindow()
    bad = _full_check(w.root)
    shot(w.root, f"audio_setup_{lang}")
    # 按键模式 + 最长的改键报错: 改键那一行最宽的状态
    w.listen_mode.set("toggle")
    w._on_listen_mode()
    w.key_msg.config(text=i18n.t("这个键游戏里要用(指令菜单/编队/移动), 换一个"))
    bad += _full_check(w.root)
    shot(w.root, f"audio_setup_toggle_{lang}")
    w.close()
    fails += _report("audio_setup", lang, bad)

    # --- 上手校准 (worker 只在点开始后才启动, 构建无副作用) ---
    from calibrate import CalibrateGUI
    cg = CalibrateGUI()
    bad = _full_check(cg.root)
    shot(cg.root, f"calibrate_{lang}")
    cg.running = False
    cg.root.destroy()
    fails += _report("calibrate", lang, bad)

    # --- 指令复盘 ---
    from review import ReviewGUI
    rv = ReviewGUI()
    bad = _full_check(rv.root)
    shot(rv.root, f"review_{lang}")
    rv.root.destroy()
    fails += _report("review", lang, bad)

    # --- 游戏指令树 ---
    from order_tree import OrderTreeWindow
    ot = OrderTreeWindow(lang=lang)
    bad = _full_check(ot.root)
    shot(ot.root, f"order_tree_{lang}")
    ot.root.destroy()
    fails += _report("order_tree", lang, bad)

    # --- 测试模式 (stub 掉模型加载) ---
    import stt

    class _Stub:
        def __init__(self, cfg):
            raise RuntimeError("stub: ui audit")

    real = stt.Transcriber
    stt.Transcriber = _Stub
    # 测试模式窗口一打开就在线程里"模型没下过就先下载": 审计不能真联网下 1.6GB
    # (2026-09-09 新用户态跑审计, 30 秒内往仓库根目录 models/ 灌了 275MB 半截文件)
    import models
    real_dl = models.download
    models.download = lambda *a, **k: True
    try:
        from listen import ListenGUI
        lg = ListenGUI()
        bad = _full_check(lg.root)
        shot(lg.root, f"listen_{lang}")
        lg.running = False
        lg.root.destroy()
    finally:
        stt.Transcriber = real
        models.download = real_dl
    fails += _report("listen", lang, bad)

    return fails


def _report(name, lang, bad):
    if not bad:
        print(f"  ✓ {name} [{lang}] 无截断")
        return 0
    print(f"  ✗✗✗ {name} [{lang}] 有 {len(bad)} 处截断:")
    for cls, text, actual, need in bad:
        print(f"        {cls}「{text}」 实际{actual} < 需要{need}")
    return 1


def main():
    total = 0
    # 语言写回 settings (各窗口构建时读它), 结束恢复原值
    orig_lang = i18n.read_lang()
    for lang in ("zh", "en"):
        print(f"=== 语言: {lang} ===")
        save_yaml_setting("stt", "language", lang)
        i18n.set_lang(lang)
        total += audit(lang)
    save_yaml_setting("stt", "language", orig_lang)
    print()
    if total:
        print(f"❌ {total} 个窗口有截断, 修完再跑。截图: {SHOT_DIR}")
        sys.exit(1)
    print(f"✓ 全部窗口两种语言无截断。截图存档: {SHOT_DIR}")


if __name__ == "__main__":
    main()
