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
        bad = find_clipped(win.root)
        shot(win.root, f"launcher_{lang}")
        win.root.destroy()
    finally:
        L._read_language = orig
    fails += _report("launcher", lang, bad)

    # --- 指令词典 ---
    from command_gui import CommandGUI
    g = CommandGUI()
    bad = find_clipped(g.root)
    shot(g.root, f"command_gui_{lang}")
    g.root.destroy()
    fails += _report("command_gui", lang, bad)

    # --- 音频设置 (会开麦克风音量流, 构建后立即关) ---
    from audio_setup import SetupWindow
    w = SetupWindow()
    bad = find_clipped(w.root)
    shot(w.root, f"audio_setup_{lang}")
    w.close()
    fails += _report("audio_setup", lang, bad)

    # --- 测试模式 (stub 掉模型加载) ---
    import stt

    class _Stub:
        def __init__(self, cfg):
            raise RuntimeError("stub: ui audit")

    real = stt.Transcriber
    stt.Transcriber = _Stub
    try:
        from listen import ListenGUI
        lg = ListenGUI()
        bad = find_clipped(lg.root)
        shot(lg.root, f"listen_{lang}")
        lg.running = False
        lg.root.destroy()
    finally:
        stt.Transcriber = real
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
