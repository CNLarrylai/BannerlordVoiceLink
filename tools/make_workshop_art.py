# -*- coding: utf-8 -*-
"""生成创意工坊全套贴图: 封面(640x640) + 页面示意图(1280x720 x2)。

风格统一: 深色底 #101418 + 金 #d4af37 + 卡片 #1a2026。不用 emoji(PIL 渲染成方块)。
用法: .venv\\Scripts\\python tools\\make_workshop_art.py
产物: assets/workshop_preview.png, assets/art/*.png
"""
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ART = os.path.join(ROOT, "assets", "art")

BG = (16, 20, 24)
CARD = (26, 32, 38)
GOLD = (212, 175, 55)
FG = (232, 237, 242)
DIM = (154, 164, 173)
GREEN = (125, 255, 155)
RED = (255, 138, 138)


def font(name, size):
    try:
        return ImageFont.truetype(rf"C:\Windows\Fonts\{name}", size)
    except OSError:
        return ImageFont.load_default()


def center(d, cx, y, text, fnt, fill):
    b = d.textbbox((0, 0), text, font=fnt)
    d.text((cx - (b[2] - b[0]) / 2, y), text, font=fnt, fill=fill)
    return b[3] - b[1]


def mic_icon(d, cx, cy, s, color):
    """极简麦克风图形 (代替 emoji)。s=整体高度。"""
    w = s * 0.36
    d.rounded_rectangle([cx - w / 2, cy - s * 0.5, cx + w / 2, cy + s * 0.05],
                        radius=int(w / 2), fill=color)
    d.arc([cx - s * 0.38, cy - s * 0.25, cx + s * 0.38, cy + s * 0.3],
          start=0, end=180, fill=color, width=max(3, int(s * 0.06)))
    d.line([cx, cy + s * 0.3, cx, cy + s * 0.45], fill=color,
           width=max(3, int(s * 0.06)))
    d.line([cx - s * 0.18, cy + s * 0.45, cx + s * 0.18, cy + s * 0.45],
           fill=color, width=max(3, int(s * 0.06)))


def cover():
    """封面 640x640。"""
    W = H = 640
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 10], fill=GOLD)
    d.rectangle([0, H - 10, W, H], fill=GOLD)

    mic_icon(d, W / 2, 118, 96, GOLD)
    center(d, W / 2, 190, "骑砍语音指挥", font("msyhbd.ttc", 58), GOLD)
    center(d, W / 2, 272, "用嘴指挥你的军队", font("msyh.ttc", 26), FG)

    rows = [("「骑兵冲锋」", "0.1秒响应"),
            ("「骑兵进攻弓箭手」", "真·锁定编队"),
            ("「骑兵分队」「左队进攻」", "一分为二包抄")]
    y = 336
    f_cmd = font("msyhbd.ttc", 26)
    f_tag = font("msyh.ttc", 18)
    for cmd, tag in rows:
        d.rounded_rectangle([46, y, W - 46, y + 62], radius=12, fill=CARD)
        d.text((66, y + 15), cmd, font=f_cmd, fill=FG)
        b = d.textbbox((0, 0), tag, font=f_tag)
        d.text((W - 66 - (b[2] - b[0]), y + 20), tag, font=f_tag, fill=GREEN)
        y += 76
    center(d, W / 2, 578, "本地离线识别 · 不联网不上传 · BETA",
           font("msyh.ttc", 19), DIM)
    p = os.path.join(ROOT, "assets", "workshop_preview_zh.png")   # 中文版留档, 工坊用双语版
    img.save(p)
    print("封面:", p)


def shot_commands():
    """示意图1: 指令速查 1280x720。"""
    W, H = 1280, 720
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 8], fill=GOLD)
    center(d, W / 2, 28, "一句话,军队照办 —— 指令速查", font("msyhbd.ttc", 40), GOLD)

    cols = [
        ("兵种", ["步兵 · 弓箭手", "骑兵 · 骑射", "全军 · 第N队"]),
        ("机动", ["冲锋 / 出击", "前进 / 后退", "撤退 / 跟我来", "别动 / 回来"]),
        ("阵型", ["盾墙 / 散开", "圆阵 / 方阵", "三角阵 / 一字排开", "排成一列"]),
        ("战术", ["自由射击 / 停火", "上马 / 下马", "打他们(集火)", "交给AI"]),
    ]
    cw = 284
    x = 34
    f_h = font("msyhbd.ttc", 30)
    f_i = font("msyh.ttc", 25)
    for title, items in cols:
        d.rounded_rectangle([x, 100, x + cw, 560], radius=14, fill=CARD)
        d.rectangle([x, 100, x + cw, 152], fill=(38, 46, 54))
        center(d, x + cw / 2, 110, title, f_h, GOLD)
        yy = 176
        for it in items:
            center(d, x + cw / 2, yy, it, f_i, FG)
            yy += 62
        x += cw + 24

    center(d, W / 2, 596, "组合随意:「弓箭手左队待命」「第五队进攻骑兵」「全军慢慢推进」",
           font("msyh.ttc", 26), GREEN)
    center(d, W / 2, 648, "口语也认识: 开干 · 怼上去 · 龟起来 · 别扎堆 · 火力全开",
           font("msyh.ttc", 24), DIM)
    p = os.path.join(ART, "shot1_commands.png")
    img.save(p)
    print("示意图1:", p)


def shot_split():
    """示意图2: 定向进攻+分队 战场俯视示意 1280x720。"""
    W, H = 1280, 720
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 8], fill=GOLD)
    center(d, W / 2, 28, "定向锁定 · 一分为二 · 左右包抄", font("msyhbd.ttc", 40), GOLD)

    # 敌我阵线示意: 上方敌军两队, 下方我方骑兵分成左右两半
    def troop(cx, cy, color, label, sub=""):
        for i in range(3):
            for j in range(4):
                d.rectangle([cx - 66 + j * 36, cy - 30 + i * 26,
                             cx - 46 + j * 36, cy - 12 + i * 26], fill=color)
        center(d, cx, cy + 58, label, font("msyhbd.ttc", 27), color)
        if sub:
            center(d, cx, cy + 94, sub, font("msyh.ttc", 21), DIM)

    troop(380, 170, RED, "敌·弓箭手")
    troop(900, 170, RED, "敌·骑兵")
    troop(330, 470, GOLD, "骑兵左队", "= 第三队")
    troop(950, 470, GOLD, "骑兵右队", "= 第五队")

    # 攻击箭头 (交叉包抄)
    def arrow(x1, y1, x2, y2):
        d.line([x1, y1, x2, y2], fill=GREEN, width=7)
        import math
        a = math.atan2(y2 - y1, x2 - x1)
        for da in (2.6, -2.6):
            d.line([x2, y2, x2 + 26 * math.cos(a + da),
                    y2 + 26 * math.sin(a + da)], fill=GREEN, width=7)

    arrow(370, 400, 400, 268)
    arrow(910, 400, 880, 268)

    # 语音气泡
    d.rounded_rectangle([330, 560, 950, 664], radius=18, fill=CARD)
    center(d, 640, 574, "「骑兵分队!」", font("msyhbd.ttc", 30), FG)
    center(d, 640, 616, "「骑兵左队进攻弓箭手!骑兵右队进攻骑兵!」",
           font("msyhbd.ttc", 28), GREEN)
    p = os.path.join(ART, "shot2_split.png")
    img.save(p)
    print("示意图2:", p)


def promo_4x3():
    """4:3 主视觉 1024x768 —— 纯图形叙事, 文案只留六个大字。

    构图: 上方暮色天光渐变, 中央声波自麦克风扩散, 下方军阵剪影(长矛列)
    正随声波推进 —— "声音驱动军队"一眼可读, 不靠一句说明文字。
    """
    W, H = 1024, 768
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    horizon = 452          # 地平线
    title_y = 568          # 标题基线区(军阵不许越过)

    # 天光: 顶部深蓝紫 -> 地平线暖金
    top, warm = (17, 21, 33), (92, 66, 40)
    for y in range(horizon):
        t = (y / horizon) ** 2.4
        d.line([0, y, W, y],
               fill=tuple(int(top[i] + (warm[i] - top[i]) * t) for i in range(3)))
    for y in range(horizon, H):     # 地面向下压暗, 给标题让出对比
        t = (y - horizon) / (H - horizon)
        v = int(24 - 16 * t)
        d.line([0, y, W, y], fill=(v, v + 2, v + 5))

    cx, cy = W / 2, 232

    # 声波: 麦克风向下方军阵扩散的同心弧(越远越淡)
    for i, r in enumerate(range(100, 372, 52)):
        fade = 1 - i / 7.2
        col = tuple(int(BG[j] + (GOLD[j] - BG[j]) * fade * 0.8) for j in range(3))
        d.arc([cx - r, cy - r, cx + r, cy + r], start=212, end=328,
              fill=col, width=max(2, int(6 * fade)))

    mic_icon(d, cx, cy, 118, GOLD)

    # 军阵剪影: 两排长矛兵贴着地平线, 近大远小
    def rank(y, n, scale, col):
        span = W * (0.60 + 0.36 * scale)
        step = span / (n - 1)
        for k in range(n):
            x = cx - span / 2 + step * k
            bw, bh = 11 * scale, 34 * scale
            d.rectangle([x - bw / 2, y - bh, x + bw / 2, y], fill=col)
            d.ellipse([x - bw * 0.6, y - bh - bw * 1.1,
                       x + bw * 0.6, y - bh + bw * 0.1], fill=col)
            sp = 64 * scale
            d.line([x + bw * 0.5, y - bh * 0.6,
                    x + bw * 0.5 + sp * 0.24, y - bh * 0.6 - sp],
                   fill=col, width=max(1, int(2.4 * scale)))

    rank(horizon + 16, 30, 0.58, (34, 38, 46))
    rank(horizon + 66, 21, 0.82, (22, 26, 32))

    # 六个大字(自适应字号, 保证两侧留白) + 上下细金线
    target = int(W * 0.72)
    size = 108
    while size > 60:
        f = font("msyhbd.ttc", size)
        b = d.textbbox((0, 0), "骑砍语音指挥", font=f)
        if b[2] - b[0] <= target:
            break
        size -= 4
    tw, th = b[2] - b[0], b[3] - b[1]
    d.text((cx - tw / 2, title_y), "骑砍语音指挥", font=f, fill=GOLD)
    ly = title_y + th + 42
    d.line([cx - tw / 2, ly, cx + tw / 2, ly], fill=GOLD, width=3)

    p = os.path.join(ART, "promo_4x3.png")
    img.save(p)
    print("4:3 主视觉:", p)


def cover_en():
    """640x640 双语封面(工坊 previewfile): 英文为主 + 中文副标题。
    英文标题用 Segoe UI Bold(Windows 自带, 无衬线粗体, 和金色底最搭);
    中文用微软雅黑粗体。三张指令卡全英文, 底部一行双语保证。"""
    W, H = 640, 640
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 10], fill=GOLD)
    d.rectangle([0, H - 10, W, H], fill=GOLD)

    mic_icon(d, W / 2, 96, 74, GOLD)

    # 标题: VOICE COMMANDER (自适应字号) / for Mount & Blade II: Bannerlord / 骑砍语音指挥
    title = "VOICE COMMANDER"
    size = 60
    while size > 40:
        f_t = font("segoeuib.ttf", size)
        b = d.textbbox((0, 0), title, font=f_t)
        if b[2] - b[0] <= W - 80:
            break
        size -= 2
    center(d, W / 2, 148, title, f_t, GOLD)
    center(d, W / 2, 222, "for Mount & Blade II: Bannerlord", font("seguisb.ttf", 22), FG)
    center(d, W / 2, 258, "骑砍语音指挥 · 用嘴指挥你的军队", font("msyhbd.ttc", 21), DIM)

    # 三张指令卡: 说法(左) + 卖点(右, 绿)
    cards = [
        ('"Cavalry, charge!"', "0.2s response"),
        ('"Cavalry, charge their archers!"', "real target lock"),
        ('"Cavalry, split!"  "Left, charge!"', "split & flank"),
    ]
    f_cmd = font("seguisb.ttf", 23)
    f_tag = font("seguisb.ttf", 16)
    y = 318
    for cmd, tag in cards:
        d.rounded_rectangle([46, y, W - 46, y + 62], radius=12, fill=CARD)
        d.text((66, y + 17), cmd, font=f_cmd, fill=FG)
        b = d.textbbox((0, 0), tag, font=f_tag)
        d.text((W - 66 - (b[2] - b[0]), y + 22), tag, font=f_tag, fill=GREEN)
        y += 76

    center(d, W / 2, 566, "Offline · No cloud · Free · BETA", font("seguisb.ttf", 18), DIM)
    center(d, W / 2, 594, "本地离线识别 · 不联网不上传", font("msyh.ttc", 15), DIM)

    for name in ("workshop_preview_en.png", "workshop_preview.png"):   # 后者=工坊 previewfile
        img.save(os.path.join(ROOT, "assets", name))
    print("双语封面: assets/workshop_preview.png (中文旧版留在 workshop_preview_zh.png)")


def main():
    os.makedirs(ART, exist_ok=True)
    cover()
    shot_commands()
    shot_split()
    promo_4x3()
    cover_en()


if __name__ == "__main__":
    main()
