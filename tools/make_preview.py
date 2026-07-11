# -*- coding: utf-8 -*-
"""生成创意工坊过渡宣传图 assets/workshop_preview.png。

风格与 app 一致(深色底+金字)。有视频封面后可直接替换这张。
用法: .venv\\Scripts\\python tools\\make_preview.py
"""
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "assets", "workshop_preview.png")

BG = (16, 20, 24)
GOLD = (212, 175, 55)
FG = (232, 237, 242)
DIM = (154, 164, 173)
GREEN = (125, 255, 155)

W, H = 640, 640


def font(name, size):
    for p in (rf"C:\Windows\Fonts\{name}", name):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def center(draw, cx, y, text, fnt, fill):
    b = draw.textbbox((0, 0), text, font=fnt)
    draw.text((cx - (b[2] - b[0]) / 2, y), text, font=fnt, fill=fill)


def main():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    # 顶部金色描边条
    d.rectangle([0, 0, W, 8], fill=GOLD)
    d.rectangle([0, H - 8, W, H], fill=GOLD)

    yh = font("msyhbd.ttc", 30)
    yh_big = font("msyhbd.ttc", 52)
    yh_mid = font("msyh.ttc", 24)
    yh_sm = font("msyh.ttc", 20)

    center(d, W / 2, 130, "骑砍语音指挥", yh_big, GOLD)
    center(d, W / 2, 210, "Bannerlord Voice Commander", yh_mid, FG)
    center(d, W / 2, 258, "用嘴指挥你的军队 · Command by voice", yh_sm, DIM)

    # 命令示例卡片
    lines = [
        "「骑兵冲锋」   → charge",
        "「骑兵打他们弓箭手」 → 定向锁定",
        "「骑兵分队」「左队进攻」 → 一分为二",
    ]
    y = 350
    for ln in lines:
        d.rounded_rectangle([70, y, W - 70, y + 54], radius=10, fill=(26, 32, 38))
        center(d, W / 2, y + 14, ln, yh, GREEN if "分队" in ln else FG)
        y += 68

    center(d, W / 2, 566, "本地离线识别 · 直播浮层 · 真·锁定编队", yh_sm, DIM)
    center(d, W / 2, 596, "BETA — 欢迎反馈", yh_sm, GOLD)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img.save(OUT)
    print(f"已生成: {OUT}  ({os.path.getsize(OUT)//1024} KB)")


if __name__ == "__main__":
    main()
