# -*- coding: utf-8 -*-
"""给剪好的成片自动叠"当前指令"注释卡, 按 YouTube 规格重编码一次。

用法:
  .venv\\Scripts\\python.exe tools\\annotate_video.py "H:\\...\\成片.mp4" [--pos topright|bottomleft]
        [--show 3.5] [--legend 起,止 ...] [--dry-run] [--events 时间表.csv]

流程:
  1. faster-whisper(GPU) 逐词转写成片音轨
  2. 按指令短语表模糊匹配, 定位每条指令说完的时刻 → 卡在其后 0.15s 弹出
  3. 落盘 <成片>_注释时间表.csv + <成片>_注释核对.jpg (每张卡一帧), 先核对再渲染
  4. PyAV 解码 → 命中窗口的帧用 PIL 叠卡 → h264_nvenc(cq19, high, GOP 30, B 帧 2)
     音频原样 remux(不重编码), moov 前置。1080p60 输出约 20 Mbps, 满足 YouTube 推荐。
  --dry-run 只做 1~3 不渲染; --events 跳过转写, 直接用你改过的时间表渲染。
"""
import os, sys, io, csv, re, json, argparse, difflib, time
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

# ---------------- 指令短语表: 短语 → 类别 ----------------
CATS = {
    "move":   ("MOVEMENT",         (120, 170, 255), "F-key"),
    "form":   ("FORMATION",        (140, 200, 160), "F-key"),
    "fire":   ("FIRE CONTROL",     (200, 200, 120), "F-key"),
    "target": ("TARGETED ATTACK",  (255, 150,  70), "mod only"),
    "split":  ("SPLIT & POSITION", (255, 210,  90), "mod only"),
    "ai":     ("AI TACTICS",       (255, 100, 120), "mod only"),
}
GROUPS = ["infantry", "archers", "cavalry", "horse archers", "all units", "everyone",
          "group five", "group six", "archers left", "archers right", "cavalry left", "cavalry right"]
# 动词短语 → 类别 (兵种在前面任意)
VERBS = [
    ("move in front of the infantry", "split"), ("move in front of the archers", "split"),
    ("go to the left of the archers", "split"), ("go to the right of the archers", "split"),
    ("go to the right of the infantry", "split"), ("go to the left of the infantry", "split"),
    ("split", "split"),
    ("hold the high ground", "ai"), ("skirmish", "ai"), ("flank", "ai"), ("advance carefully", "ai"),
    ("guard the left flank", "ai"), ("guard the right flank", "ai"), ("protect the archers", "ai"),
    ("attack them", "target"), ("charge their archers", "target"), ("charge their horse archers", "target"),
    ("charge their infantry", "target"), ("charge their cavalry", "target"),
    ("attack their infantry", "target"), ("attack their archers", "target"), ("attack their horse archers", "target"),
    ("attack infantry", "target"), ("attack horse archers", "target"), ("attack archers", "target"),
    ("shield wall", "form"), ("shoot wall", "form"), ("shields up", "form"), ("line formation", "form"), ("loose formation", "form"), ("spread out", "form"),
    ("wedge", "form"), ("circle", "form"), ("square", "form"), ("column", "form"), ("scatter", "form"), ("line", "form"),
    ("fire at will", "fire"), ("hold fire", "fire"),
    ("follow me", "move"), ("charge", "move"), ("fall back", "move"), ("retreat", "move"), ("halt", "move"),
    ("advance", "move"), ("move back", "move"), ("come back", "move"), ("go there", "move"), ("move here", "move"),
    ("skimish", "ai"), ("scumish", "ai"),
]
# 卡片上显示的规范说法 (含 Whisper 常见错听的归一)
DISPLAY = {"line": "line formation", "shoot wall": "shield wall", "skimish": "skirmish", "scumish": "skirmish",
           "attack infantry": "attack their infantry", "attack archers": "attack their archers",
           "attack horse archers": "attack their horse archers"}

def norm(w):
    return re.sub(r"[^a-z' ]", "", w.lower()).strip()

# ---------------- 1. 逐词转写 ----------------
def transcribe_words(path):
    import models, cuda_libs; cuda_libs.add_to_search_path()
    from faster_whisper import WhisperModel
    m = WhisperModel("large-v3-turbo", device="cuda", compute_type="float16")
    segs, _ = m.transcribe(path, language="en", beam_size=5, vad_filter=True, word_timestamps=True,
        initial_prompt="Bannerlord voice commands: infantry, archers, cavalry, horse archers, shield wall, "
                       "loose formation, line formation, fire at will, charge, skirmish, flank, split, "
                       "hold the high ground, advance carefully, attack them, follow me.")
    words = []
    for s in segs:
        for w in s.words or []:
            t = norm(w.word)
            if t: words.append((t, w.start, w.end))
    return words

# ---------------- 2. 匹配指令 ----------------
def find_commands(words):
    toks = [w for w, _, _ in words]
    found = []   # (end_time, start_time, display, cat, score)
    for phrase, cat in VERBS:
        pt = phrase.split(); L = len(pt)
        for i in range(0, len(toks) - L + 1):
            win = " ".join(toks[i:i + L])
            r = difflib.SequenceMatcher(None, win, phrase).ratio()
            if r < 0.82: continue
            # 往前找兵种 (最多 3 个词内)
            grp = None
            for g in sorted(GROUPS, key=len, reverse=True):
                gt = g.split(); j = i - len(gt)
                if j >= 0 and difflib.SequenceMatcher(None, " ".join(toks[j:i]), g).ratio() >= 0.8:
                    grp = g; break
            if grp is None and i >= 1:  # 单词兵种模糊 (archer/archers)
                for g in ("infantry", "archers", "cavalry"):
                    if difflib.SequenceMatcher(None, toks[i - 1], g).ratio() >= 0.75: grp = g; break
            if grp is None:
                continue   # 真指令总是"兵种 + 动作"; 旁白里裸提到的 split/flank/attack them 不算
            disp = DISPLAY.get(phrase, phrase)
            text = grp.capitalize() + ", " + disp
            found.append((words[i + L - 1][2], words[i][1] if grp is None else words[max(0, i - len(grp.split()))][1], text, cat, r, L))
    # 去重: 同一位置更长短语优先; 2 秒内重复同文本只留一个
    found.sort(key=lambda x: (x[0], -x[5], -x[4]))
    out = []
    for f in found:
        if any(abs(f[0] - o[0]) < 1.5 for o in out): continue   # 同一时刻已有更长/更早的匹配
        if out and out[-1][2] == f[2] and f[0] - out[-1][0] < 5.0: continue   # 5 秒内重喊同一条: 一张卡
        out.append(f)
    return [(round(e, 2), round(s, 2), text, cat) for e, s, text, cat, _, _ in out]

# ---------------- 卡片 ----------------
from PIL import Image, ImageDraw, ImageFont
F_BOLD = r"C:\Windows\Fonts\arialbd.ttf"; F_REG = r"C:\Windows\Fonts\segoeui.ttf"; F_BADGE = r"C:\Windows\Fonts\bahnschrift.ttf"

def command_card(text, cat, corner="right"):
    name, col, tag = CATS[cat]
    f1 = ImageFont.truetype(F_BOLD, 44); f2 = ImageFont.truetype(F_BADGE, 25); f3 = ImageFont.truetype(F_REG, 25)
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    w1 = tmp.textlength("\u201c" + text + "\u201d", font=f1); w2 = tmp.textlength(name, font=f2); w3 = tmp.textlength(tag, font=f3)
    W = int(max(w1, w2 + w3 + 60) + 110); H = 140
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, W - 1, H - 1), radius=20, fill=(12, 12, 16, 196))
    bar = (W - 14, 0, W - 1, H - 1) if corner == "right" else (0, 0, 14, H - 1)
    d.rounded_rectangle(bar, radius=7, fill=col + (255,))
    x0 = 34 if corner == "right" else 44
    d.text((x0, 20), "\u201c" + text + "\u201d", font=f1, fill=(255, 255, 255, 255))
    bx, by, bw, bh = x0, 86, int(w2 + 30), 36
    d.rounded_rectangle((bx, by, bx + bw, by + bh), radius=10, fill=col + (255,))
    d.text((bx + 15, by + 4), name, font=f2, fill=(20, 20, 24, 255))
    d.text((bx + bw + 14, by + 4), tag, font=f3, fill=(210, 210, 210, 255))
    return img

def legend_card():
    f0 = ImageFont.truetype(F_BOLD, 34); f1 = ImageFont.truetype(F_BADGE, 28); f2 = ImageFont.truetype(F_REG, 24)
    W, H = 560, 60 + 52 * len(CATS) + 20
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, W - 1, H - 1), radius=22, fill=(12, 12, 16, 196))
    d.text((28, 16), "Voice commands in this mod", font=f0, fill=(255, 255, 255, 255))
    y = 66
    for k, (name, col, tag) in CATS.items():
        d.ellipse((30, y + 8, 50, y + 28), fill=col + (255,)); d.text((66, y), name, font=f1, fill=(255, 255, 255, 255))
        tw = d.textlength(tag, font=f2)
        d.text((W - 28 - tw, y + 3), tag, font=f2, fill=col + (255,) if tag == "mod only" else (170, 170, 170, 255))
        y += 52
    return img

def fit(img, W):
    """卡片按 1080p 设计, 其它分辨率等比缩放 (4K = ×2)。"""
    s = W / 1920
    return img if abs(s - 1) < 1e-3 else img.resize((int(img.width * s), int(img.height * s)), Image.LANCZOS)

def place(img, pos, W=1920, H=1080):
    s = W / 1920
    if pos == "topright":   return (W - img.width - int(40 * s), int(220 * s))   # 避开顶部横幅与右侧伤亡面板
    if pos == "bottomleft": return (int(40 * s), int(780 * s))                    # 避开左下战斗记录与右下摄像头
    if pos == "topleft":    return (int(40 * s), int(210 * s))
    raise ValueError(pos)

# ---------------- 3/4. 时间表 + 渲染 ----------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video"); ap.add_argument("--pos", default="topright", choices=["topright", "bottomleft"])
    ap.add_argument("--show", type=float, default=3.5); ap.add_argument("--delay", type=float, default=0.15)
    ap.add_argument("--cq", type=int, default=20, help="NVENC 质量, 越小越清晰体积越大 (18~23)")
    ap.add_argument("--legend", nargs="*", default=[], help="图例卡窗口, 形如 33,43")
    ap.add_argument("--events", help="跳过转写, 用这份时间表 csv 渲染"); ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    src = a.video; stem = os.path.splitext(src)[0]
    csvp = a.events or stem + "_注释时间表.csv"

    import av
    ic = av.open(src); vs = ic.streams.video[0]; W, H, fps = vs.width, vs.height, float(vs.average_rate)
    dur = ic.duration / 1e6; ic.close()
    print(f"源: {W}x{H} @{fps:g}fps {dur:.1f}s")

    if not a.events:
        t0 = time.time(); words = transcribe_words(src); print(f"转写 {len(words)} 词, {time.time()-t0:.0f}s")
        cmds = find_commands(words)
        rows = []
        for i, (end, start, text, cat) in enumerate(cmds):
            on = round(end + a.delay, 2); off = round(min(dur, on + a.show), 2)
            if i + 1 < len(cmds): off = min(off, round(cmds[i + 1][0] + a.delay - 0.3, 2))
            rows.append({"出现": on, "消失": off, "指令": text, "类别": cat, "说的时刻": start})
        with io.open(csvp, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["出现", "消失", "指令", "类别", "说的时刻"]); w.writeheader(); w.writerows(rows)
        print(f"识别到 {len(rows)} 条指令 → {csvp}")
        for r in rows: print(f"  {r['出现']:7.2f}  {r['指令']:42s} {CATS[r['类别']][0]}")
    else:
        rows = list(csv.DictReader(io.open(csvp, encoding="utf-8-sig")))
        for r in rows: r["出现"] = float(r["出现"]); r["消失"] = float(r["消失"])

    # 叠层清单
    layers = []   # (on, off, PIL, (x,y))
    for r in rows:
        img = fit(command_card(r["指令"], r["类别"], "right" if a.pos == "topright" else "left"), W)
        layers.append((r["出现"], r["消失"], img, place(img, a.pos, W, H)))
    if a.legend:
        lg = fit(legend_card(), W)
        for win in a.legend:
            s, e = [float(x) for x in win.split(",")]; layers.append((s, e, lg, place(lg, "topleft", W, H)))

    # 核对图: 每张卡出现后 0.5s 抽一帧
    ic = av.open(src); vs = ic.streams.video[0]
    tiles = []
    for on, off, img, xy in layers:
        ic.seek(int((on + 0.5) * 1e6))
        for fr in ic.decode(vs):
            bg = fr.to_image().convert("RGBA"); bg.alpha_composite(img, xy); tiles.append((on, bg.resize((480, 270)))); break
    ic.close()
    if tiles:
        cols = 4; rows_n = (len(tiles) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * 480, rows_n * 290), "black"); d = ImageDraw.Draw(sheet)
        for i, (on, im) in enumerate(tiles):
            x = (i % cols) * 480; y = (i // cols) * 290; sheet.paste(im.convert("RGB"), (x, y + 20)); d.text((x + 4, y + 3), f"{on:.1f}s", fill="yellow")
        sheet.save(stem + "_注释核对.jpg", quality=85); print("核对图 →", stem + "_注释核对.jpg")
    if a.dry_run:
        print("dry-run, 不渲染"); return

    # 渲染
    out = stem + "_注释版.mp4"
    ic = av.open(src); vs = ic.streams.video[0]; vs.thread_type = "AUTO"; as_ = ic.streams.audio[0]
    oc = av.open(out, "w", options={"movflags": "faststart"})
    ov = oc.add_stream("h264_nvenc", rate=Fraction(fps).limit_denominator(1000)); ov.time_base = Fraction(1, 90000)
    ov.width, ov.height, ov.pix_fmt = W, H, "yuv420p"
    # cq 20 ≈ 1080p60 20 Mbps / 4K30 45 Mbps, 都在 YouTube 推荐值(12 / 35-45)之上
    ov.options = {"preset": "p5", "tune": "hq", "rc": "vbr", "cq": str(a.cq), "b": "0", "maxrate": "80M", "bufsize": "160M",
                  "profile": "high", "g": str(int(round(fps / 2))), "bf": "2", "spatial-aq": "1", "temporal-aq": "1"}
    try:
        oa = oc.add_stream_from_template(as_); remux = True
    except Exception:
        oa = oc.add_stream(template=as_); remux = True
    t0 = time.time(); n = 0; total = int(dur * fps); active = sorted(layers, key=lambda l: l[0])
    for pk in ic.demux(vs, as_):
        if pk.stream.type == "audio":
            if pk.dts is None: continue
            pk.stream = oa; oc.mux(pk); continue
        for fr in pk.decode():
            t = float(fr.pts * vs.time_base) if fr.pts is not None else n / fps
            hits = [l for l in active if l[0] <= t < l[1]]
            if hits:
                bg = fr.to_image().convert("RGBA")
                for on, off, img, xy in hits: bg.alpha_composite(img, xy)
                nf = av.VideoFrame.from_image(bg.convert("RGB"))
            else:
                nf = fr
            nf.pts = int(round(t * 90000)); nf.time_base = Fraction(1, 90000)
            for p in ov.encode(nf): oc.mux(p)
            n += 1
            if n % (total // 10 or 1) == 0: print(f"  {100*n//total}%  {n/(time.time()-t0):.0f} fps", flush=True)
    for p in ov.encode(): oc.mux(p)
    oc.close(); ic.close()
    sz = os.path.getsize(out); print(f"完成 → {out}  {sz/1e6:.0f} MB  ≈{sz*8/dur/1e6:.1f} Mbps  用时 {time.time()-t0:.0f}s")

if __name__ == "__main__":
    main()
