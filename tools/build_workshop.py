# -*- coding: utf-8 -*-
"""一键构建"创意工坊整包": 模组 DLL + 语音程序 EXE 组装进游戏 Modules。

产物 = <游戏>/Modules/BannerlordVoiceLink/
        ├─ SubModule.xml
        ├─ bin/Win64_Shipping_Client/BannerlordVoiceLink.dll
        └─ VoiceApp/  (整个 PyInstaller 包, 含内置 base 模型)
这份目录就是工坊上传源: 订阅者一次拿到全部, 开游戏时模组自动拉起语音程序。

打包前把 settings.yaml 临时净化成"发行默认"(麦克风=系统默认/模型=auto/中文),
打完自动还原你本机的值 —— 你的 Voicemeeter 设备名不会被发出去。

用法: .venv/Scripts/python tools/build_workshop.py [--skip-exe]
"""
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = r"C:\SteamLibraryforstream\steamapps\common\Mount & Blade II Bannerlord"
MOD_DST = os.path.join(GAME, "Modules", "BannerlordVoiceLink")
SETTINGS = os.path.join(ROOT, "config", "settings.yaml")
PY = sys.executable

# 发行默认值: (行匹配正则, 替换行)
SHIP_DEFAULTS = [
    (r"^  device: .*$", "  device: null", "audio"),          # 麦克风=系统默认
    (r"^  model: .*$", "  model: auto", "stt"),              # 模型跟随硬件
    (r"^  device: .*$", "  device: auto", "stt"),            # 运行方式自动
    (r"^  language: .*$", "  language: zh", "stt"),          # 默认中文
]


def sanitize_settings(content):
    """从给定内容(不是文件! 防止先截断后读空)生成发行默认配置。"""
    lines = content.splitlines(keepends=True)
    section = None
    for i, line in enumerate(lines):
        if re.match(r"^\S", line):
            section = line.split(":")[0]
        for pat, repl, sec in SHIP_DEFAULTS:
            if section == sec and re.match(pat, line):
                lines[i] = repl + "\n"
                break
    return "".join(lines)


def run(cmd, **kw):
    print("  $", " ".join(str(c) for c in cmd))
    subprocess.run(cmd, check=True, cwd=ROOT, **kw)


def mod_version():
    """模组版本 = v<应用版本>.<git提交数> —— 每次有改动提交必然递增,
    launcher 的 Mods 页直接可见, 用户一眼判断'即将打开的是不是新版'。"""
    sys.path.insert(0, os.path.join(ROOT, "src"))
    from version import APP_VERSION
    try:
        n = subprocess.run(["git", "rev-list", "--count", "HEAD"], cwd=ROOT,
                           capture_output=True, text=True,
                           check=True).stdout.strip()
    except Exception:
        n = "0"
    return f"v{APP_VERSION}.{n}"


def stamped_submodule_xml(ver):
    """读仓库 SubModule.xml, 把 Version 换成构建版本号, 返回文本。"""
    p = os.path.join(ROOT, "mod", "BannerlordVoiceLink", "SubModule.xml")
    with open(p, encoding="utf-8") as f:
        content = f.read()
    return re.sub(r'<Version value="[^"]*"',
                  f'<Version value="{ver}"', content, count=1)


def main():
    skip_exe = "--skip-exe" in sys.argv

    ver = mod_version()
    print(f"== 1/4 构建并部署模组 DLL (版本 {ver}) ==")
    run(["dotnet", "build", "-c", "Release",
         os.path.join(ROOT, "mod", "BannerlordVoiceLink")])
    os.makedirs(os.path.join(MOD_DST, "bin", "Win64_Shipping_Client"), exist_ok=True)
    # 部署的 SubModule.xml 打上构建版本戳 —— launcher Mods 页可见, 方便核对新旧
    with open(os.path.join(MOD_DST, "SubModule.xml"), "w", encoding="utf-8") as f:
        f.write(stamped_submodule_xml(ver))
    try:
        shutil.copy(os.path.join(ROOT, "mod", "BannerlordVoiceLink", "bin",
                                 "Release", "BannerlordVoiceLink.dll"),
                    os.path.join(MOD_DST, "bin", "Win64_Shipping_Client"))
    except PermissionError:
        print("  !! DLL 被占用(游戏/launcher开着?), 跳过 DLL 更新 — 关掉后重跑")

    if not skip_exe:
        print("== 2/4 打包语音程序 EXE (临时净化配置, 完毕自动还原) ==")
        with open(SETTINGS, encoding="utf-8") as f:
            backup = f.read()
        sanitized = sanitize_settings(backup)
        assert sanitized.strip(), "净化后的配置为空, 拒绝打包"
        try:
            with open(SETTINGS, "w", encoding="utf-8") as f:
                f.write(sanitized)
            run([os.path.join(ROOT, ".venv", "Scripts", "pyinstaller.exe"),
                 "app.spec", "--noconfirm"])
        finally:
            with open(SETTINGS, "w", encoding="utf-8") as f:
                f.write(backup)
            print("  已还原本机配置。")

    print("== 3/4 组装 VoiceApp 进模组目录 ==")
    src = os.path.join(ROOT, "dist", "BannerlordVoice")
    dst = os.path.join(MOD_DST, "VoiceApp")
    if not os.path.isdir(src):
        print("!! dist/BannerlordVoice 不存在, 先不带 --skip-exe 跑一次")
        sys.exit(1)
    # 运行中的打包版会锁住 VoiceApp 文件 —— 先给人话提示, 不甩堆栈
    chk = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command",
         "(Get-Process BannerlordVoice -ErrorAction SilentlyContinue).Count"],
        capture_output=True, text=True)
    if (chk.stdout or "").strip() not in ("", "0"):
        print("!! 有 BannerlordVoice.exe 正在运行 (自动弹出的语音面板?),")
        print("   请先关掉那些窗口再重跑本脚本。")
        sys.exit(1)
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst)

    print("== 4/4 体检 ==")
    total = 0
    for dp, _, files in os.walk(MOD_DST):
        for fn in files:
            total += os.path.getsize(os.path.join(dp, fn))
    print(f"  整包大小: {total / 1048576:.0f} MB")
    for must in ("SubModule.xml",
                 os.path.join("bin", "Win64_Shipping_Client",
                              "BannerlordVoiceLink.dll"),
                 os.path.join("VoiceApp", "BannerlordVoice.exe")):
        ok = os.path.exists(os.path.join(MOD_DST, must))
        print(f"  {'✓' if ok else '✗✗✗ 缺'} {must}")
        if not ok:
            sys.exit(1)
    # 随包配置必须是"发行默认"(有内容 + 麦克风null + 中文) —— 防打空/带私人设备名
    shipped = os.path.join(MOD_DST, "VoiceApp", "_internal", "config",
                           "settings.yaml")
    with open(shipped, encoding="utf-8") as f:
        cfg = f.read()
    for token in ("device: null", "model: auto", "language: zh"):
        ok = token in cfg
        print(f"  {'✓' if ok else '✗✗✗ 随包配置错'} {token}")
        if not ok:
            sys.exit(1)
    print(f"\n✓ 工坊整包就绪: {MOD_DST}")
    print(f"  模组版本: {ver}  ← 开游戏前在 launcher Mods 页核对这个号")
    print("  上传方式见 mod/PUBLISH.md")


if __name__ == "__main__":
    main()
