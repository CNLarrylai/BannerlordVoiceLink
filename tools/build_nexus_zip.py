# -*- coding: utf-8 -*-
"""把已部署的正式包(游戏 Modules/BannerlordVoiceLink)压成 Nexus Mods 用的 zip。

前提: 先跑过 `build_workshop.py --release`(SubModule.xml 里名字不带 [DEV])。
zip 结构 = 根目录就是 `BannerlordVoiceLink/`(docs/nexus-description.md 的安装说明:
解压得到一个文件夹, 放进游戏 Modules 即可; Vortex 也认这种"模块文件夹在根"的布局)。

用法: .venv\\Scripts\\python tools\\build_nexus_zip.py [--allow-dev]
产物: dist/nexus/VoiceCommander_v<版本>.zip (+ .sha256), dist/ 已 gitignore。
"""
import hashlib
import os
import re
import sys
import time
import zipfile

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = r"C:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord"
MOD = os.path.join(GAME, "Modules", "BannerlordVoiceLink")
OUT_DIR = os.path.join(ROOT, "dist", "nexus")
SKIP_NAMES = {"autostart_off.txt", "__pycache__", "Thumbs.db", "desktop.ini"}


def main():
    sub = os.path.join(MOD, "SubModule.xml")
    if not os.path.isfile(sub):
        sys.exit(f"✗ 没找到已部署的模组: {sub}  (先跑 build_workshop.py --release)")
    with open(sub, encoding="utf-8") as f:
        xml = f.read()
    name = re.search(r'<Name value="([^"]*)"', xml).group(1)
    ver = re.search(r'<Version value="([^"]*)"', xml).group(1)
    if "[DEV]" in name and "--allow-dev" not in sys.argv:
        sys.exit(f"✗ 部署的是开发版 ({name})。先跑 build_workshop.py --release, 或加 --allow-dev")
    for must in ("bin\\Win64_Shipping_Client\\BannerlordVoiceLink.dll", "VoiceApp\\BannerlordVoice.exe"):
        if not os.path.isfile(os.path.join(MOD, must)):
            sys.exit(f"✗ 缺 {must}")

    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, f"VoiceCommander_{ver}.zip")
    if os.path.exists(out):
        os.remove(out)
    t0 = time.time()
    n = 0
    raw = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for root, dirs, files in os.walk(MOD):
            dirs[:] = [d for d in dirs if d not in SKIP_NAMES]
            for fn in files:
                if fn in SKIP_NAMES:
                    continue
                p = os.path.join(root, fn)
                arc = "BannerlordVoiceLink/" + os.path.relpath(p, MOD).replace("\\", "/")
                z.write(p, arc)
                n += 1
                raw += os.path.getsize(p)
                if n % 200 == 0:
                    print(f"  … {n} 个文件, {raw/1e6:.0f} MB", flush=True)
    size = os.path.getsize(out)
    h = hashlib.sha256()
    with open(out, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    with open(out + ".sha256", "w", encoding="utf-8") as f:
        f.write(f"{h.hexdigest()}  {os.path.basename(out)}\n")
    print(f"\n✓ Nexus 包: {out}")
    print(f"  模组名 {name}  版本 {ver}")
    print(f"  {n} 个文件, 原始 {raw/1e6:.0f} MB -> zip {size/1e6:.0f} MB, 用时 {time.time()-t0:.0f}s")
    print(f"  sha256 {h.hexdigest()[:16]}…  (完整值在 {os.path.basename(out)}.sha256)")
    print("  上传: Nexus 文件版本填 " + ver.lstrip("v") + "; 说明见 docs/nexus-description.md")


if __name__ == "__main__":
    main()
