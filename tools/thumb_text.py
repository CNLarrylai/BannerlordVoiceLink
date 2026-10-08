# -*- coding: utf-8 -*-
"""给封面底图加一行 YouTube 风格大字, 输出 1280x720 JPEG (<2MB)。

用法:
  python tools\\thumb_text.py 底图.png "no *keyboard...*" -o 封面.jpg
  python tools\\thumb_text.py 底图.png "it just *listens...*" --y 60 --size 132
  python tools\\thumb_text.py 底图.png "NO *KEYBOARD*" --style shout --tilt -4
  python tools\\thumb_text.py 底图.png "bannerlord update|*NEW STARTS*|LOOTING" --style shout   # | 分行

  *星号包住的词* = 黄色, 其余白色。--style:
    round : 小写、圆润黑体、白+黄、深描边+软阴影 (参照"i was wrong..."那类)
    shout : 大写、更粗、可倾斜、白+黄、粗描边 (参照"LORD OF THE RINGS PUBLIC RELEASE"那类)
  底图任意尺寸, 自动居中裁到 16:9; --enhance 提饱和对比 (游戏截图建议开, AI 生图一般不用)。
"""
import argparse, os, re
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter

FONTS = {"round": r"C:\Windows\Fonts\seguibl.ttf", "shout": r"C:\Windows\Fonts\impact.ttf"}
WHITE, YELLOW, DARK = (255, 255, 255), (255, 222, 0), (18, 18, 28)

def parse_words(s):
    """'no *keyboard...*' → [('no', WHITE), ('keyboard...', YELLOW)]"""
    out = []
    for tok in re.findall(r"\*[^*]+\*|\S+", s):
        if tok.startswith("*") and tok.endswith("*"): out.append((tok[1:-1], YELLOW))
        else: out.append((tok, WHITE))
    return out

def fit_169(im, W=1280, H=720, top=None):
    """裁到 16:9。top: 竖图/方图裁剪起点(0~1 的比例), 不给则居中。"""
    r = im.width / im.height
    if r > W / H: nw = int(im.height * W / H); im = im.crop(((im.width - nw) // 2, 0, (im.width - nw) // 2 + nw, im.height))
    else:
        nh = int(im.width * H / W); y0 = (im.height - nh) // 2 if top is None else int(min(max(top, 0), 1) * (im.height - nh))
        im = im.crop((0, y0, im.width, y0 + nh))
    return im.resize((W, H), Image.LANCZOS)

def draw_line(im, words, y, font, sw, gap, tilt=0, align="center", x0=60):
    d = ImageDraw.Draw(im); space = font.getlength(" ") * (1 + gap)
    widths = [font.getlength(t) for t, _ in words]; total = sum(widths) + space * (len(words) - 1)
    layer = Image.new("RGBA", (int(total + sw * 4 + 40), int(font.size * 1.5)), (0, 0, 0, 0)); ld = ImageDraw.Draw(layer)
    x = sw * 2 + 20
    for (t, col), w in zip(words, widths):
        ld.text((x, 0), t, font=font, fill=col, stroke_width=sw, stroke_fill=DARK); x += w + space
    if tilt: layer = layer.rotate(tilt, resample=Image.BICUBIC, expand=True)
    # 软阴影
    sh = Image.new("RGBA", layer.size, (0, 0, 0, 0)); sh.paste((0, 0, 0, 180), mask=layer.split()[3]); sh = sh.filter(ImageFilter.GaussianBlur(10))
    px = (im.width - layer.width) // 2 if align == "center" else (x0 - sw * 2 - 20 if align == "left" else im.width - layer.width - x0)
    base = im.convert("RGBA"); base.alpha_composite(sh, (px + 6, y + 10)); base.alpha_composite(layer, (px, y))
    return base.convert("RGB")

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("image"); ap.add_argument("text", help="用 | 分行, *词* 为黄色")
    ap.add_argument("-o", "--out"); ap.add_argument("--style", default="round", choices=["round", "shout"])
    ap.add_argument("--size", type=int); ap.add_argument("--y", type=int, default=40); ap.add_argument("--tilt", type=float, default=0)
    ap.add_argument("--enhance", action="store_true"); ap.add_argument("--darken-top", type=int, default=0, help="顶部压暗高度(px), 天空太亮时用")
    ap.add_argument("--top", type=float, help="方图/竖图裁剪起点 0~1 (0=顶, 1=底), 默认居中")
    ap.add_argument("--align", default="center", choices=["center", "left", "right"]); ap.add_argument("--x", type=int, default=60, help="左/右对齐时的边距")
    a = ap.parse_args()
    im = fit_169(Image.open(a.image).convert("RGB"), top=a.top)
    if a.enhance:
        im = ImageEnhance.Color(im).enhance(1.3); im = ImageEnhance.Contrast(im).enhance(1.12); im = ImageEnhance.Brightness(im).enhance(1.04)
    if a.darken_top:
        m = Image.new("L", im.size, 0); md = ImageDraw.Draw(m)
        for i in range(a.darken_top): md.line([(0, i), (im.width, i)], fill=int(160 * (1 - i / a.darken_top)))
        im = Image.composite(Image.new("RGB", im.size, (0, 0, 0)), im, m)
    lines = [parse_words(s.strip()) for s in a.text.split("|") if s.strip()]
    size = a.size or (132 if len(lines) == 1 else 108)
    sw = 11 if a.style == "round" else 9
    font = ImageFont.truetype(FONTS[a.style], size)
    if a.style == "shout":
        lines = [[(t.upper(), c) for t, c in ln] for ln in lines]
    y = a.y
    for ln in lines:
        im = draw_line(im, ln, y, font, sw, 0.28 if a.style == "round" else 0.15, a.tilt, a.align, a.x); y += int(size * 1.12)
    out = a.out or os.path.splitext(a.image)[0] + "_封面.jpg"
    q = 92
    while True:
        im.save(out, quality=q)
        if os.path.getsize(out) < 1_900_000 or q <= 70: break
        q -= 5
    print(out, round(os.path.getsize(out) / 1e6, 2), "MB")

if __name__ == "__main__":
    main()
