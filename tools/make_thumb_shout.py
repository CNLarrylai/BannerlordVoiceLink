# -*- coding: utf-8 -*-
"""把"喊话"人像照抠图+镜像, 叠到战场底图上做 1280x720 视频封面。

用法:
  python tools\\make_thumb_shout.py 人像.jpg --base knight --text "BANNERLORD|*VOICE COMMAND*" -o 封面.jpg

  人像自带背景即可, 走 rembg(u2net_human_seg)抠图; --mirror 默认开(照片里朝右 → 镜像后朝左,
  放画面右侧朝军队喊)。--base knight=骑士底图, field=大军底图(整张左右翻转, 让声波从右往左扫)。
  --erase 传多边形顶点(抠图前坐标, x,y;x,y...)擦掉椅背等和人相连的杂物。
  嘴的位置用 --mouth 指定(抠图后坐标), 声波弧线/射线从嘴发出。
"""
import argparse, math, os, sys

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from thumb_text import FONTS, draw_line, parse_words

W, H = 1280, 720
ART = {
    "knight": r"H:\2025录制\粗剪_语音指挥\剪映初稿\gemini_v1_thumb_source.png",
    "field": r"H:\2025录制\粗剪_语音指挥\剪映初稿\gemini_v1_commander_panel.png",
}
CYAN, GOLD = (125, 228, 255), (255, 230, 85)


def cutout(path, crop, erase, cache):
    """rembg 抠图 + 擦杂物, 结果缓存(抠一次要几秒)。"""
    if cache and os.path.exists(cache):
        return Image.open(cache).convert("RGBA")
    from rembg import new_session, remove
    im = Image.open(path).convert("RGB")
    if crop:
        im = im.crop(crop)
    out = remove(im, session=new_session("u2net_human_seg"), post_process_mask=True)
    if erase:
        m = Image.new("L", out.size, 255)
        ImageDraw.Draw(m).polygon(erase, fill=0)
        m = m.filter(ImageFilter.GaussianBlur(1.2))
        out.putalpha(Image.composite(out.split()[3], Image.new("L", out.size, 0), m))
    out = out.crop(out.split()[3].getbbox())
    if cache:
        out.save(cache)
    return out


def rot_pt(p, wh, angle):
    """图片绕中心旋转 angle 度(expand=True)后, 点 p 的新坐标。"""
    w, h = wh
    th = math.radians(angle)
    x, y = p[0] - w / 2.0, p[1] - h / 2.0
    nx = x * math.cos(th) + y * math.sin(th)
    ny = -x * math.sin(th) + y * math.cos(th)
    nw = abs(w * math.cos(th)) + abs(h * math.sin(th))
    nh = abs(w * math.sin(th)) + abs(h * math.cos(th))
    return (nx + nw / 2.0, ny + nh / 2.0)


def load_base(kind):
    if kind == "knight":
        im = Image.open(ART["knight"]).convert("RGB").resize((W, H), Image.LANCZOS)
        # 原图右侧那块"指令面板"UI 要让位给人像: 渐变压暗 + 景深模糊
        g = Image.new("L", (W, H), 0)
        gd = ImageDraw.Draw(g)
        for x in range(640, W):
            gd.line([(x, 0), (x, H)], fill=int(228 * min(1.0, (x - 640) / 150.0)))
        g = g.filter(ImageFilter.GaussianBlur(18))
        im = Image.composite(im.filter(ImageFilter.GaussianBlur(6)), im,
                             g.point(lambda v: min(255, int(v * 1.8))))
        im = Image.composite(Image.new("RGB", (W, H), (9, 10, 15)), im, g)
    else:
        # 大军底图左右翻转: AI 指挥官被翻到画框外, 声波改成从右往左扫
        im = Image.open(ART["field"]).convert("RGB").transpose(Image.FLIP_LEFT_RIGHT)
        im = im.crop((0, 230, 2132, 230 + 1199)).resize((W, H), Image.LANCZOS)
        im = ImageEnhance.Brightness(im).enhance(0.88)           # 压一档, 让声波/光锥打得出来
        v = Image.new("L", (W, H), 0)                            # 四边暗角
        ImageDraw.Draw(v).ellipse([-int(W * 0.30), -int(H * 0.34),
                                   int(W * 1.30), int(H * 1.34)], fill=255)
        v = v.filter(ImageFilter.GaussianBlur(150)).point(lambda t: int((255 - t) * 0.72))
        im = Image.composite(Image.new("RGB", (W, H), (6, 7, 12)), im, v)
    im = ImageEnhance.Color(im).enhance(1.16)
    return ImageEnhance.Contrast(im).enhance(1.08)


def prep_portrait(cut, mouth, ph, tilt, mirror):
    p = Image.new("RGBA", (cut.width + 40, cut.height + 20), (0, 0, 0, 0))
    p.paste(cut, (20, 20))                       # 左/上/右留空, 免得白描边压出直线
    mx, my = mouth[0] + 20, mouth[1] + 20
    if mirror:
        p = p.transpose(Image.FLIP_LEFT_RIGHT)
        mx = p.width - mx
    s = ph / p.height
    p = p.resize((max(1, int(p.width * s)), ph), Image.LANCZOS)
    mx, my = mx * s, my * s
    p = ImageEnhance.Color(p).enhance(1.12)
    p = ImageEnhance.Contrast(p).enhance(1.10)
    wh = p.size
    p = p.rotate(tilt, resample=Image.BICUBIC, expand=True)
    return p, rot_pt((mx, my), wh, tilt)


def shout_fx(canvas, mouth, reach, ray_end, cone_a=70, spread=21):
    """从嘴向左轰出去: 喇叭光锥 + 近处同心声波弧 + 锥内短射线。"""
    fx = 2
    mx, my = mouth[0] * fx, mouth[1] * fx

    # 光锥(先画、重模糊, 当成底光)
    cone = Image.new("RGBA", (W * fx, H * fx), (0, 0, 0, 0))
    cd = ImageDraw.Draw(cone)
    far = 1700 * fx
    for half, al in ((spread, cone_a), (spread * 0.55, int(cone_a * 1.2))):
        a = math.radians(half)
        cd.polygon([(mx, my),
                    (mx - far, my - math.tan(a) * far),
                    (mx - far, my + math.tan(a) * far)], fill=(150, 228, 255, al))
    cone = cone.resize((W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(26))
    canvas.alpha_composite(cone)

    lay = Image.new("RGBA", (W * fx, H * fx), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for i, r in enumerate(range(165 * fx, reach * fx, 108 * fx)):
        al = int(225 * (1 - i / 4.0))
        if al <= 0:
            break
        half = spread + 9
        d.arc([mx - r, my - r, mx + r, my + r], 180 - half, 180 + half,
              fill=CYAN + (al,), width=max(4, int(11 * fx - i * 3)))
    for ang in (-15, -5, 5, 15):
        a = math.radians(180 + ang)
        d.line([mx + math.cos(a) * 140 * fx, my + math.sin(a) * 140 * fx,
                mx + math.cos(a) * ray_end * 0.62 * fx,
                my + math.sin(a) * ray_end * 0.62 * fx],
               fill=GOLD + (165,), width=int(3 * fx))
    lay = lay.resize((W, H), Image.LANCZOS)
    canvas.alpha_composite(lay.filter(ImageFilter.GaussianBlur(11)))
    canvas.alpha_composite(lay)


def zoom_blur(im, center, strength, steps=8, amt=0.06):
    """以嘴为中心的缩放模糊: 越远越拉丝, 给一股"声浪轰出去"的冲击感。"""
    if strength <= 0:
        return im
    cx, cy = center
    acc = im.copy()
    for i in range(1, steps + 1):
        s = 1 + amt * i / steps
        big = im.resize((int(W * s), int(H * s)), Image.BILINEAR)
        ox, oy = int(cx * s - cx), int(cy * s - cy)
        acc = Image.blend(acc, big.crop((ox, oy, ox + W, oy + H)), 1.0 / (i + 1))
    m = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(m)
    for r in range(900, 140, -20):                     # 由外向内画同心圆: 外圈强, 中心不动
        v = int(255 * min(1.0, (r - 140) / 700.0))
        md.ellipse([cx - r, cy - r, cx + r, cy + r], fill=v)
    m = m.filter(ImageFilter.GaussianBlur(40)).point(lambda t: int(t * strength))
    return Image.composite(acc, im, m)


def chip(im, text, xy, tilt=-3, size=46):
    f = ImageFont.truetype(FONTS["shout"], size)
    card = Image.new("RGBA", (int(f.getlength(text)) + 62, int(size * 1.85)), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle([0, 0, card.width - 1, card.height - 1], 14,
                        fill=(12, 16, 26, 210), outline=CYAN + (235,), width=3)
    d.text((31, size * 0.3), text, font=f, fill=GOLD)
    card = card.rotate(tilt, resample=Image.BICUBIC, expand=True)
    b = im.convert("RGBA")
    b.alpha_composite(card, xy)
    return b.convert("RGB")


def build(cut, a, out):
    base = load_base(a.base)
    p, mouth = prep_portrait(cut, a.mouth, a.height, a.ptilt, not a.no_mirror)
    px = a.x if a.x is not None else W - p.width + 210
    py = H - p.height + 26
    m = (px + mouth[0], py + mouth[1])
    canvas = zoom_blur(base, m, a.zoom).convert("RGBA")
    shout_fx(canvas, m, a.reach, a.ray, a.cone)
    sh = Image.new("RGBA", p.size, (0, 0, 0, 0))
    sh.paste((0, 0, 0, 185), mask=p.split()[3])
    canvas.alpha_composite(sh.filter(ImageFilter.GaussianBlur(20)), (px - 18, py + 12))
    ol = Image.new("RGBA", p.size, (0, 0, 0, 0))
    ol.paste((255, 255, 255, 255), mask=p.split()[3].filter(ImageFilter.MaxFilter(15)))
    canvas.alpha_composite(ol, (px, py))
    canvas.alpha_composite(p, (px, py))
    im = canvas.convert("RGB")

    # 左下角压暗, 保标题可读
    g = Image.new("L", (W, H), 0)
    gd = ImageDraw.Draw(g)
    for y in range(H - 300, H):
        gd.line([(0, y), (int(W * 0.62), y)], fill=int(120 * (y - (H - 300)) / 300.0))
    im = Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), im,
                         g.filter(ImageFilter.GaussianBlur(40)))

    if a.chip:
        im = chip(im, a.chip, tuple(a.chip_xy))
    lines = [[(t.upper(), c) for t, c in parse_words(s.strip())]
             for s in a.text.split("|") if s.strip()]
    size = a.size                                   # 标题自动缩到不怼上人像
    while size > 60:
        f = ImageFont.truetype(FONTS["shout"], size)
        sp = f.getlength(" ") * 1.15
        if max(sum(f.getlength(t) for t, _ in ln) + sp * (len(ln) - 1) for ln in lines) <= a.maxw:
            break
        size -= 2
    if size != a.size:
        print("  标题按 maxw=%d 自动缩到 %dpx" % (a.maxw, size))
    a.size = size
    font = ImageFont.truetype(FONTS["shout"], a.size)
    y = H - int(a.size * 1.12 * len(lines)) - 30
    for ln in lines:
        im = draw_line(im, ln, y, font, 9, 0.15, a.tilt, "left", 44)
        y += int(a.size * 1.12)

    q = 92
    while True:
        im.save(out, quality=q)
        if os.path.getsize(out) < 1_900_000 or q <= 70:
            break
        q -= 6
    print("%s  %.0f KB" % (out, os.path.getsize(out) / 1024))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("portrait")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--base", default="knight", choices=sorted(ART))
    ap.add_argument("--text", default="BANNERLORD|*VOICE COMMAND*", help="| 分行, *词* 黄色")
    ap.add_argument("--size", type=int, default=104)
    ap.add_argument("--tilt", type=float, default=-3, help="标题倾斜")
    ap.add_argument("--crop", help="抠图前裁剪 l,t,r,b")
    ap.add_argument("--erase", help="抠图后擦除多边形 x,y;x,y;...")
    ap.add_argument("--cache", help="抠图结果缓存 png")
    ap.add_argument("--mouth", default="600,362", help="抠图后嘴的坐标 x,y")
    ap.add_argument("--height", type=int, default=650, help="人像高度(px)")
    ap.add_argument("--ptilt", type=float, default=-5, help="人像倾斜")
    ap.add_argument("--x", type=int, help="人像左边缘 x, 默认贴右并出画框")
    ap.add_argument("--no-mirror", action="store_true")
    ap.add_argument("--reach", type=int, default=560, help="声波弧最远半径")
    ap.add_argument("--ray", type=int, default=340, help="射线最远半径")
    ap.add_argument("--cone", type=int, default=28, help="喇叭光锥强度 0~150")
    ap.add_argument("--zoom", type=float, default=0.55, help="以嘴为中心的缩放模糊强度 0~1")
    ap.add_argument("--maxw", type=int, default=720, help="标题最大宽度(px), 超了自动缩字号")
    ap.add_argument("--chip", help="嘴前指令卡文字")
    ap.add_argument("--chip-xy", default="300,300")
    a = ap.parse_args()
    a.mouth = tuple(int(v) for v in a.mouth.split(","))
    a.chip_xy = [int(v) for v in a.chip_xy.split(",")]
    crop = tuple(int(v) for v in a.crop.split(",")) if a.crop else None
    erase = [tuple(int(v) for v in pt.split(",")) for pt in a.erase.split(";")] if a.erase else None
    build(cutout(a.portrait, crop, erase, a.cache), a, a.out)


if __name__ == "__main__":
    main()
