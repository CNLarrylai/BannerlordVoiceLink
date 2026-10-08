# -*- coding: utf-8 -*-
r"""英文指令速查示意图 (工坊图库用, 1920x1080)。

内容来源 config/commands.yaml 的 en 别名 (每条取最口语的一个说法), 分四栏 +
战术层一条横带 (需伴侣模组)。风格沿用 make_workshop_art: 深底 + 金 + 卡片。
用法: .venv\Scripts\python tools\make_commands_en.py
产物: assets/art/shot3_commands_en.png
"""
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ART = os.path.join(ROOT, "assets", "art")
BASE = os.path.join(ART, "cover_base_2048.jpg")

BG = (14, 18, 26)
CARD = (24, 30, 40)
CARD_HEAD = (36, 44, 58)
GOLD = (222, 184, 78)
GOLD_HI = (248, 222, 140)
FG = (236, 240, 245)
DIM = (160, 170, 182)
GREEN = (140, 235, 165)


def font(name, size):
    return ImageFont.truetype(rf"C:\Windows\Fonts\{name}", size)


def center(d, cx, y, text, f, fill):
    b = d.textbbox((0, 0), text, font=f)
    d.text((cx - (b[2] - b[0]) / 2 - b[0], y), text, font=f, fill=fill)
    return b[3] - b[1]


def backdrop(W, H):
    """底图: 封面原画拉暗做纹理, 上面压深色, 保证文字对比。"""
    img = Image.new("RGB", (W, H), BG)
    try:
        art = Image.open(BASE).convert("RGB")
        s = W / art.width
        art = art.resize((W, int(art.height * s)), Image.LANCZOS)
        top = int(art.height * 0.30)           # 取地平线附近那一段
        art = art.crop((0, top, W, top + H)).filter(ImageFilter.GaussianBlur(6))
        img = Image.blend(img, art, 0.22)
    except OSError:
        pass
    return img


def main():
    W, H = 1920, 1080
    img = backdrop(W, H)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 8], fill=GOLD)

    f_title = font("georgiab.ttf", 58)
    f_sub = font("seguisb.ttf", 26)
    f_head = font("segoeuib.ttf", 30)
    f_item = font("seguisb.ttf", 25)
    f_note = font("segoeui.ttf", 21)

    center(d, W / 2, 34, "SUPPORTED VOICE COMMANDS", f_title, GOLD)
    center(d, W / 2, 112, "Say the unit, then the order  ·  \"Archers, hold fire\"  ·  \"All units, charge\"",
           f_sub, FG)

    cols = [
        ("UNITS", [
            "Infantry  ·  Archers",
            "Cavalry  ·  Horse archers",
            "All units  ·  Everyone",
            "Group 5 / 6 / 7 / 8",
            "Cavalry left  ·  Cavalry right",
            "(after \"Cavalry, split\")",
        ]),
        ("MOVEMENT", [
            "Charge",
            "Advance",
            "Fall back",
            "Halt  ·  Hold position",
            "Retreat",
            "Follow me",
            "Move here",
        ]),
        ("FORMATIONS", [
            "Line",
            "Shield wall",
            "Loose  ·  Spread out",
            "Circle",
            "Square",
            "Wedge",
            "Column",
            "Scatter",
        ]),
        ("FIRE & MISC", [
            "Fire at will",
            "Hold fire",
            "Mount  ·  Dismount",
            "Face this way",
            "AI control",
            "Manual control",
            "(take back from AI)",
        ]),
    ]
    margin, gap = 56, 28
    cw = (W - margin * 2 - gap * 3) / 4
    top, bottom = 176, 700
    x = margin
    for head, items in cols:
        d.rounded_rectangle([x, top, x + cw, bottom], radius=16, fill=CARD)
        d.rounded_rectangle([x, top, x + cw, top + 58], radius=16, fill=CARD_HEAD)
        d.rectangle([x, top + 40, x + cw, top + 58], fill=CARD_HEAD)
        center(d, x + cw / 2, top + 10, head, f_head, GOLD)
        yy = top + 84
        for it in items:
            col = DIM if it.startswith("(") else FG
            center(d, x + cw / 2, yy, it, f_item, col)
            yy += 54 if not it.startswith("(") else 38
        x += cw + gap

    # 战术层横带 (需伴侣模组)
    by0, by1 = 736, 990
    d.rounded_rectangle([margin, by0, W - margin, by1], radius=16, fill=CARD)
    d.rectangle([margin, by0, margin + 10, by1], fill=GOLD)
    d.text((margin + 36, by0 + 18), "TACTICS  —  beyond the keyboard (companion mod, included)",
           font=f_head, fill=GOLD)
    tactics = [
        ('"Cavalry, charge their archers"', "true target lock on that enemy formation"),
        ('"Attack them"', "focus-fire the enemy nearest to your crosshair"),
        ('"Cavalry, split"  →  "Cavalry left, charge"', "two halves, commanded separately"),
        ('"Flank"  ·  "Skirmish"  ·  "Hold the high ground"', "AI-level maneuvers, still under your command"),
        ('"Protect the archers"  ·  "Guard the left flank"', "screen the flank, engage what comes close"),
        ('"Infantry, go to the right of the archers"', "relative positioning, left/right from your view"),
    ]
    f_cmd = font("seguisb.ttf", 25)
    cx1, cx2 = margin + 36, margin + 36 + 900
    yy = by0 + 74
    for i, (cmd, why) in enumerate(tactics):
        px = cx1 if i % 2 == 0 else cx2
        if i % 2 == 0 and i:
            yy += 68
        d.text((px, yy), cmd, font=f_cmd, fill=FG)
        d.text((px, yy + 32), why, font=f_note, fill=GREEN)

    center(d, W / 2, 1022, "Offline speech recognition  ·  ~0.1 s response  ·  say it your way, "
           "wording is fuzzy-matched  ·  fix a mishear once with F11 and it learns",
           f_note, DIM)

    p = os.path.join(ART, "shot3_commands_en.png")
    img.save(p, optimize=True)
    print("英文指令图:", p, os.path.getsize(p) // 1024, "KB")


if __name__ == "__main__":
    main()
