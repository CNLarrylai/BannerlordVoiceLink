"""生成应用图标 —— 深色圆底 + "令"字。

icon.ico      金色 (正式版, 会发按键)
icon_test.ico 灰色 (测试模式, 只听不发键)
"""
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets")
os.makedirs(OUT, exist_ok=True)

SIZE = 256


def make(filename, color, text="令"):
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # 深色圆底 + 描边
    margin = 8
    d.ellipse([margin, margin, SIZE - margin, SIZE - margin], fill=(16, 20, 24, 255))
    d.ellipse([margin, margin, SIZE - margin, SIZE - margin],
              outline=color, width=10)

    # "令" 字 (微软雅黑加粗)
    font = None
    for path in (r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\msyh.ttc"):
        if os.path.exists(path):
            font = ImageFont.truetype(path, 150)
            break
    if font is None:
        raise SystemExit("找不到微软雅黑字体")

    bbox = d.textbbox((0, 0), text, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text(((SIZE - w) / 2 - bbox[0], (SIZE - h) / 2 - bbox[1]),
           text, font=font, fill=color)

    ico_path = os.path.join(OUT, filename)
    img.save(ico_path, sizes=[(256, 256), (64, 64), (48, 48), (32, 32), (16, 16)])
    print(f"图标已生成: {ico_path}")


make("icon.ico", (212, 175, 55, 255))                 # 金色 = 正式版
make("icon_test.ico", (150, 158, 168, 255))            # 灰色 = 测试模式
make("icon_audio.ico", (95, 170, 255, 255), text="音")  # 蓝色 = 音频设置
make("icon_cmd.ico", (125, 255, 155, 255), text="典")   # 绿色 = 指令词典
