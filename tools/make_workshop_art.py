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
    p = os.path.join(ROOT, "assets", "workshop_preview.png")
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


def main():
    os.makedirs(ART, exist_ok=True)
    cover()
    shot_commands()
    shot_split()


if __name__ == "__main__":
    main()
