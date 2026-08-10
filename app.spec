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
# 整活包示例 (首次运行播种到用户配置目录, 之后永不覆盖)
for _f in glob.glob(os.path.join(ROOT, "config", "fun", "*.yaml")):
    datas.append((_f, "config/fun"))
binaries = []
hiddenimports = [
    # app.py 及各处是函数内条件导入, 显式列出保证被打进去
    "launcher", "main", "listen", "audio_setup", "command_gui",
    "matcher", "executor", "stt", "audio", "overlay", "paths",
    "license", "version", "machine_id",
    # 后加的模块(多为函数内 import, 静态分析易漏)
    "i18n", "models", "retry", "modlink", "dictionary", "usage",
    "procman", "order_tree", "calibrate", "cuda_libs", "stream_asr", "review",
    "donation",
    "yaml", "rapidfuzz", "pydirectinput", "keyboard", "numpy",
]

# 内置流式 zipformer (混合识别快路, 只带 int8 encoder 省体积 ≈191MB)
_STREAM = os.path.join(
    ROOT, "kws", "models",
    "sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20")
for f in ("encoder-epoch-99-avg-1.int8.onnx", "decoder-epoch-99-avg-1.onnx",
          "joiner-epoch-99-avg-1.int8.onnx", "tokens.txt"):
    fp = os.path.join(_STREAM, f)
    if os.path.isfile(fp):
        datas.append((fp, "models/streaming-zipformer-zh-en"))
    else:
        print(f"[spec] ⚠ 流式模型缺 {f}, 打出的包只有纯 Whisper")

# 内置 Whisper 兜底模型 (免联网; 国内 HuggingFace 首次下载常失败)。
#   small = 无显卡时的默认(CPU 1.7s/命中100%, base 只有92%);
#   base  = 保底(极弱机器手动选, 0.56s)。turbo 不内置: CPU上要6秒不能当默认,
#   有卡玩家下载 CUDA 库后由 faster-whisper 自行拉取(或手动选)。
for _m in ("small", "base"):
    _snaps = glob.glob(os.path.expanduser(
        f"~/.cache/huggingface/hub/models--Systran--faster-whisper-{_m}/snapshots/*"))
    if not _snaps:
        print(f"[spec] ⚠ 本机缺 faster-whisper-{_m} 缓存, 包内不含它")
        continue
    for f in os.listdir(_snaps[0]):
        fp = os.path.join(_snaps[0], f)
        if os.path.isfile(fp):
            datas.append((fp, f"models/faster-whisper-{_m}"))

# 这些包 PyInstaller 静态分析抓不全, 用 collect_all 兜底
for pkg in ("faster_whisper", "ctranslate2", "av", "sherpa_onnx",
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
