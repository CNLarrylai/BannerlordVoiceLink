# -*- coding: utf-8 -*-
r"""在 AI 绘画底图上叠双语标题, 生成工坊封面(previewfile)。

底图: assets/art/cover_base_2048.jpg (Gemini 出图, 2048x2048, 无文字)。
产物:
  assets/art/cover_painted_top.png / cover_painted_bottom.png   2048 原尺寸两个候选
  assets/workshop_preview.png                                   640x640 工坊 previewfile (用 top 版)
用法: .venv\Scripts\python tools\make_cover_painted.py [top|bottom]
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ART = os.path.join(ROOT, "assets", "art")
BASE = os.path.join(ART, "cover_base_2048.jpg")

GOLD = (222, 184, 78)
GOLD_HI = (248, 222, 140)
INK = (8, 10, 16)


def font(name, size):
    f = ImageFont.truetype(rf"C:\Windows\Fonts\{name}", size)
    if name.startswith("Noto") and "VF" in name:     # 可变字体默认是 Regular, 封面要粗
        try:
            f.set_variation_by_name("Bold")
        except Exception:
            pass
    return f


def fit(d, text, name, max_w, start, floor):
    size = start
    while size > floor:
        f = font(name, size)
        b = d.textbbox((0, 0), text, font=f)
        if b[2] - b[0] <= max_w:
            return f, b
        size -= 4
    return f, b


def glow_text(img, xy, text, f, fill, blur=18, shadow=(0, 0, 0, 200)):
    """先画一层模糊的深色光晕再画字, 保证任何底色上都能读。"""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    ld.text(xy, text, font=f, fill=shadow, stroke_width=10, stroke_fill=shadow)
    layer = layer.filter(ImageFilter.GaussianBlur(blur))
    img.alpha_composite(layer)
    d = ImageDraw.Draw(img)
    d.text(xy, text, font=f, fill=fill, stroke_width=3, stroke_fill=INK)


def darken_band(img, y0, y1, strength=0.72, up=True):
    """竖向渐变压暗条 (up=True: 上浅下深; False: 上深下浅)。"""
    W, H = img.size
    band = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(band)
    n = y1 - y0
    for i in range(n):
        t = i / n if up else 1 - i / n
        a = int(255 * strength * (t ** 1.6))
        bd.line([0, y0 + i, W, y0 + i], fill=(6, 8, 14, a))
    img.alpha_composite(band)


def compose(where):
    img = Image.open(BASE).convert("RGBA")
    W, H = img.size
    d = ImageDraw.Draw(img)
    cx = W / 2

    lines = ["VOICE", "COMMANDER"]        # 英文标题拆两行, 字号按最长的一行定
    sub_zh = "骑砍语音指挥"
    tag = "for Mount & Blade II: Bannerlord"

    f_t, bt = fit(d, "COMMANDER", "georgiab.ttf", int(W * 0.58), 300, 120)
    f_zh, bz = fit(d, sub_zh, "NotoSerifSC-VF.ttf", int(W * 0.46), 150, 80)
    f_tag = font("georgiai.ttf", 56)
    btg = d.textbbox((0, 0), tag, font=f_tag)
    tw, th = bt[2] - bt[0], bt[3] - bt[1]
    zw, zh = bz[2] - bz[0], bz[3] - bz[1]
    gw = btg[2] - btg[0]
    lead = int(th * 0.22)                   # 两行之间的行距
    block_h = th * 2 + lead + 40 + 36 + zh + 36 + (btg[3] - btg[1])

    if where == "top":
        darken_band(img, 0, int(H * 0.46), strength=0.66, up=False)
        y = 100
        cx = W * 0.40          # 文字块左移, 避开右上举起的手臂
    else:
        darken_band(img, int(H * 0.52), H, strength=0.88, up=True)
        y = H - 100 - block_h

    # 主标题两行
    for ln in lines:
        b = d.textbbox((0, 0), ln, font=f_t)
        lw = b[2] - b[0]
        glow_text(img, (cx - lw / 2 - b[0], y - bt[1]), ln, f_t, GOLD)
        y += th + lead
    y += 40 - lead
    # 金线 + 中文副标题
    d = ImageDraw.Draw(img)
    line_w = int(tw * 0.95)
    for dx in (-1, 0, 1):
        d.line([cx - line_w / 2, y + dx, cx + line_w / 2, y + dx], fill=GOLD_HI)
    y += 36
    glow_text(img, (cx - zw / 2 - bz[0], y - bz[1]), sub_zh, f_zh, GOLD_HI, blur=14)
    y += zh + 36
    glow_text(img, (cx - gw / 2 - btg[0], y - btg[1]), tag, f_tag, (236, 230, 214), blur=10)

    return img.convert("RGB")


def main():
    pick = sys.argv[1] if len(sys.argv) > 1 else "top"
    out = {}
    for where in ("top", "bottom"):
        im = compose(where)
        p = os.path.join(ART, f"cover_painted_{where}.png")
        im.save(p)
        out[where] = im
        print("候选:", p)
    small = out[pick].resize((640, 640), Image.LANCZOS)
    p = os.path.join(ROOT, "assets", "workshop_preview.png")
    small.save(p, optimize=True)
    print(f"工坊 previewfile ({pick}):", p, os.path.getsize(p) // 1024, "KB")


if __name__ == "__main__":
    main()
