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


def find_game():
    """定位骑砍安装目录 —— 别写死路径(2026-08 用户移过一次库, 全链路崩)。

    顺序: 环境变量 BANNERLORD_DIR > 各 Steam 库常见位置 > 报错提示。
    判据是 bin 下的 TaleWorlds.MountAndBlade.dll 真实存在。
    """
    cands = []
    env = os.environ.get("BANNERLORD_DIR")
    if env:
        cands.append(env)
    for base in (r"C:\Program Files (x86)\Steam", r"C:\SteamLibraryforstream",
                 r"D:\Steam", r"E:\SteamLibrary", r"F:\SteamLibrary",
                 r"D:\SteamLibrary", r"C:\Steam"):
        cands.append(os.path.join(base, "steamapps", "common",
                                  "Mount & Blade II Bannerlord"))
    for c in cands:
        if os.path.exists(os.path.join(c, "bin", "Win64_Shipping_Client",
                                       "TaleWorlds.MountAndBlade.dll")):
            return c
    print("!! 找不到骑砍安装目录。请设环境变量 BANNERLORD_DIR 指向游戏根目录,")
    print("   例: setx BANNERLORD_DIR \"D:\\Steam\\steamapps\\common\\Mount & Blade II Bannerlord\"")
    sys.exit(1)


GAME = find_game()
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


def _running_count():
    """会锁住待更新文件的进程数。

    两类都会锁: ①BannerlordVoice.exe(打包版, 锁 VoiceApp) ②骑砍 launcher/游戏
    (验证/加载模组时锁 BannerlordVoiceLink.dll)。任一开着都得先关。
    """
    try:
        r = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command",
             "(Get-Process -ErrorAction SilentlyContinue | Where-Object {"
             " $_.ProcessName -match 'BannerlordVoice|Bannerlord\\.'"
             " -or $_.ProcessName -match 'TaleWorlds\\.MountAndBlade\\.Launcher'"
             " } | Measure-Object).Count"],
            capture_output=True, text=True)
        return int((r.stdout or "0").strip() or "0")
    except Exception:
        return 0


def stamped_submodule_xml(ver, release=False):
    """读仓库 SubModule.xml, 盖版本戳; 非 release 再给名字盖 [DEV] 戳。

    Modules 目录既是开发部署地也是工坊上传源 —— 默认按开发处理(名字带
    [DEV], launcher 里和工坊订阅版一眼区分); 上传工坊前必须用 --release
    重新组装一次, 出干净名字(流程见 PUBLISH.md)。模组 Id 不动(存档兼容)。
    """
    p = os.path.join(ROOT, "mod", "BannerlordVoiceLink", "SubModule.xml")
    with open(p, encoding="utf-8") as f:
        content = f.read()
    content = re.sub(r'<Version value="[^"]*"',
                     f'<Version value="{ver}"', content, count=1)
    if not release:
        content = re.sub(r'<Name value="([^"]*)"',
                         r'<Name value="\1 [DEV]"', content, count=1)
    return content


def main():
    skip_exe = "--skip-exe" in sys.argv
    release = "--release" in sys.argv
    ver = mod_version()

    # —— 预检: 运行中的打包版会锁 VoiceApp/DLL, 部分部署会留下"号新内容旧"的
    #    说谎版本。所以先检查、早退, 一个文件都别碰(教训: 版本戳曾先于复制写入)。
    if _running_count() > 0:
        print("!! 检测到会锁文件的进程正在运行:")
        print("   - BannerlordVoice.exe (打包版语音程序), 或")
        print("   - 骑砍 launcher / 游戏本体 (验证/加载模组时锁 DLL)")
        print("   请先全部关掉再重跑。本次未改动任何文件(版本号也没变, 不会说谎)。")
        sys.exit(1)

    print(f"== 1/4 构建模组 DLL ==")
    run(["dotnet", "build", "-c", "Release",
         os.path.join(ROOT, "mod", "BannerlordVoiceLink")])
    os.makedirs(os.path.join(MOD_DST, "bin", "Win64_Shipping_Client"), exist_ok=True)
    # DLL 复制失败=硬停(不"跳过", 否则会 DLL旧/版本新 不一致)
    try:
        shutil.copy(os.path.join(ROOT, "mod", "BannerlordVoiceLink", "bin",
                                 "Release", "BannerlordVoiceLink.dll"),
                    os.path.join(MOD_DST, "bin", "Win64_Shipping_Client"))
    except PermissionError:
        print("!! DLL 被锁(骑砍 launcher/游戏中途开了?)。请关掉后重跑,")
        print("   本次未写版本号, 不会出现号新内容旧。")
        sys.exit(1)

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
    if _running_count() > 0:                     # 打包途中有人开了打包版? 再挡一次
        print("!! 组装前检测到 BannerlordVoice.exe 又跑起来了, 请关掉后重跑。")
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
                 os.path.join("VoiceApp", "BannerlordVoice.exe"),
                 # 混合识别快路的流式模型(缺了会静默退回纯Whisper, 打包必须带全)
                 os.path.join("VoiceApp", "_internal", "models",
                              "streaming-zipformer-zh-en",
                              "encoder-epoch-99-avg-1.int8.onnx"),
                 os.path.join("VoiceApp", "_internal", "models",
                              "streaming-zipformer-zh-en", "tokens.txt"),
                 # 无显卡玩家的 Whisper 兜底默认(缺了会静默退回 base=92%)
                 os.path.join("VoiceApp", "_internal", "models",
                              "faster-whisper-small", "model.bin")):
        ok = os.path.exists(os.path.join(MOD_DST, must))
        print(f"  {'✓' if ok else '✗✗✗ 缺'} {must}")
        if not ok:
            sys.exit(1)
    # 随包配置必须是"发行默认"(有内容 + 麦克风null + 中文) —— 防打空/带私人设备名
    shipped = os.path.join(MOD_DST, "VoiceApp", "_internal", "config",
                           "settings.yaml")
    with open(shipped, encoding="utf-8") as f:
        cfg = f.read()
    for token in ("device: null", "model: auto", "language: zh",
                  "engine: hybrid"):
        ok = token in cfg
        print(f"  {'✓' if ok else '✗✗✗ 随包配置错'} {token}")
        if not ok:
            sys.exit(1)

    # —— 最后一步才写版本戳: 只有 DLL + VoiceApp + 体检全过, 版本号才更新。
    #    这样"launcher 显示的版本"永远等于"真正部署进去的内容", 绝不说谎。
    with open(os.path.join(MOD_DST, "SubModule.xml"), "w", encoding="utf-8") as f:
        f.write(stamped_submodule_xml(ver, release))
    tag = "RELEASE(干净名字, 可上传工坊)" if release else "[DEV] 开发版名字"
    print(f"\n✓ 整包就绪: {MOD_DST}  ({tag})")
    print(f"  模组版本: {ver}  ← 开游戏前在 launcher Mods 页核对这个号")
    if not release:
        print("  ⚠ 上传工坊前先跑: build_workshop.py --release (去掉[DEV]名字)")
    print("  上传方式见 mod/PUBLISH.md")


if __name__ == "__main__":
    main()
