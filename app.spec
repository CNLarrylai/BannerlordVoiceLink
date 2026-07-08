# -*- mode: python ; coding: utf-8 -*-
# CPU 通用版打包 —— 内置 base 模型、不含 CUDA。任何 Windows 双击即用。
#   构建: .venv\Scripts\pyinstaller app.spec --noconfirm
import glob
import os

from PyInstaller.utils.hooks import collect_all

ROOT = os.path.abspath(os.getcwd())
SRC = os.path.join(ROOT, "src")

datas = [
    (os.path.join(ROOT, "config", "settings.yaml"), "config"),
    (os.path.join(ROOT, "config", "commands.yaml"), "config"),
    (os.path.join(ROOT, "config", "order_tree.yaml"), "config"),
    (os.path.join(ROOT, "config", "calibration.yaml"), "config"),
    (os.path.join(ROOT, "assets", "icon.ico"), "assets"),
]
binaries = []
hiddenimports = [
    # app.py 及各处是函数内条件导入, 显式列出保证被打进去
    "launcher", "main", "listen", "audio_setup", "command_gui",
    "matcher", "executor", "stt", "audio", "overlay", "paths",
    "license", "version", "machine_id",
    # 后加的模块(多为函数内 import, 静态分析易漏)
    "i18n", "models", "retry", "modlink", "dictionary", "usage",
    "procman", "order_tree", "calibrate", "cuda_libs",
    "yaml", "rapidfuzz", "pydirectinput", "keyboard", "numpy",
]

# 内置 base 模型 (免联网; 国内 HuggingFace 首次下载常失败)
_snaps = glob.glob(os.path.expanduser(
    "~/.cache/huggingface/hub/models--Systran--faster-whisper-base/snapshots/*"))
if _snaps:
    for f in os.listdir(_snaps[0]):
        fp = os.path.join(_snaps[0], f)
        if os.path.isfile(fp):
            datas.append((fp, "models/faster-whisper-base"))

# 这些包 PyInstaller 静态分析抓不全, 用 collect_all 兜底
for pkg in ("faster_whisper", "ctranslate2", "av",
            "sounddevice", "soundfile", "onnxruntime", "tokenizers", "pypinyin"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception as e:
        print(f"[spec] collect_all({pkg}) 跳过: {e}")

a = Analysis(
    [os.path.join(SRC, "app.py")],
    pathex=[SRC],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    # CPU 版排除 CUDA 库(体积大); comtypes/pyttsx3 仅测试用; PIL/matplotlib 用不到
    excludes=["nvidia", "comtypes", "pyttsx3", "matplotlib", "PIL",
              "pandas", "scipy", "IPython"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="BannerlordVoice",
    console=False,          # 启动器是 GUI; voice/listen 子进程自带新控制台
    uac_admin=True,         # 请求管理员(注入按键需要)
    icon=os.path.join(ROOT, "assets", "icon.ico"),
)
coll = COLLECT(
    exe, a.binaries, a.datas,
    strip=False, upx=False,
    name="BannerlordVoice",
)
