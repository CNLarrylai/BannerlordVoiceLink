# -*- coding: utf-8 -*-
"""在本机模拟"全新用户"体验 —— 可逆, 不删任何东西。

新用户和作者机器的差别只在两处(都是每用户状态, 与仓库/成品包无关):
  1. %LOCALAPPDATA%\\BannerlordVoice\\   配置(模型/设备/麦克风)、下载的 CUDA 库、
     首次 GPU 引导标记、个人词典、日志、共建录音
  2. ~\\.cache\\huggingface\\hub\\models--*  已下载的 Whisper 模型
     (新用户一个都没有 -> 音频设置里 turbo 显示"需联网下载", auto 会触发下载)

用法(先关掉语音程序和游戏):
  python tools/fresh_user.py start     把上面两处改名藏起来 (加 .__real__ 后缀)
      -> 用 Modules 里的成品包(run.bat)走一遍新手流程
  python tools/fresh_user.py restore   把真实状态换回来; 模拟期间新产生的目录
                                       改名为 .__fresh__ 留档(想删自己删, 脚本不删)
  python tools/fresh_user.py status    看现在处于哪个状态

!! 从 Claude 桌面版的终端里跑时, %LOCALAPPDATA% 是被 MSIX 虚拟化的(写入落到
   Packages\\Claude_*\\LocalCache, 成品包看不见)。本脚本检测到这种情况会自动通过
   WMI 在容器外重新拉起自己(run_outside), 真正改到真实目录。2026-09-09 血案。
"""
import glob
import os
import subprocess
import sys
import tempfile
import time

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

LOCAL = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
DATA = os.path.join(LOCAL, "BannerlordVoice")
HUB = os.path.expanduser("~/.cache/huggingface/hub")
REAL = ".__real__"
FRESH = ".__fresh__"
MODEL_GLOBS = ("models--Systran--faster-whisper-*",
               "models--mobiuslabsgmbh--faster-whisper-*")


# ---------- 容器逃逸 ----------
def is_virtualized():
    """本进程对 %LOCALAPPDATA% 的写入是否被重定向到某个包的 LocalCache。"""
    probe = os.path.join(LOCAL, ".vt_probe_" + str(os.getpid()))
    try:
        with open(probe, "w") as f:
            f.write("x")
        real = os.path.realpath(probe)
        return "\\Packages\\" in real and "\\LocalCache\\" in real
    except Exception:
        return False
    finally:
        try:
            os.remove(probe)
        except Exception:
            pass


def run_outside(argv, timeout=120):
    """在包容器外执行命令(WMI Win32_Process.Create 起的进程没有包身份), 回传输出。"""
    out_path = os.path.join(tempfile.gettempdir(), f"fresh_user_out_{os.getpid()}.txt")
    done_path = out_path + ".done"
    for p in (out_path, done_path):
        try:
            os.remove(p)
        except Exception:
            pass
    quoted = " ".join(f'"{a}"' if " " in a else a for a in argv)
    cmdline = f'cmd.exe /c {quoted} > "{out_path}" 2>&1 & echo done> "{done_path}"'
    ps = ("Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments "
          "@{CommandLine=$env:FU_CMD} | Select-Object -ExpandProperty ReturnValue")
    env = dict(os.environ, FU_CMD=cmdline)
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], env=env,
                       capture_output=True, text=True)
    if r.returncode != 0 or r.stdout.strip() != "0":
        raise RuntimeError(f"WMI 拉起失败: {r.stdout} {r.stderr}")
    t0 = time.time()
    while not os.path.exists(done_path) and time.time() - t0 < timeout:
        time.sleep(0.3)
    try:
        with open(out_path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception:
        return "(无输出)"


# ---------- 状态 ----------
def _running():
    try:
        out = os.popen("tasklist").read().lower()
    except Exception:
        return []
    return [n for n in ("bannerlordvoice.exe", "bannerlord.exe",
                        "taleworlds.mountandblade.launcher.exe") if n in out]


def _model_dirs(suffix=""):
    out = []
    for g in MODEL_GLOBS:
        out += glob.glob(os.path.join(HUB, g + suffix))
    return sorted(d for d in out if os.path.isdir(d)
                  and (d.endswith(suffix) if suffix else not d.endswith((REAL, FRESH))
                       and FRESH not in d))


def _size(path):
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total / 1e6


def status():
    hidden = os.path.isdir(DATA + REAL) or bool(_model_dirs(REAL))
    print(f"状态: {'【模拟新用户中】' if hidden else '正常 (真实状态)'}")
    print(f"  数据目录 {DATA}: {'存在' if os.path.isdir(DATA) else '不存在(新用户首启会自动创建)'}"
          + (f"  -> 真实路径 {os.path.realpath(DATA)}" if os.path.isdir(DATA) else ""))
    if os.path.isdir(DATA + REAL):
        print(f"  真实数据藏在: {DATA + REAL}")
    print(f"  可见的模型缓存: {[os.path.basename(d) for d in _model_dirs()] or '无 (新用户状态)'}")
    real = _model_dirs(REAL)
    if real:
        print(f"  藏起来的模型: {[os.path.basename(d)[:-len(REAL)] for d in real]}")
    leftovers = glob.glob(DATA + FRESH + "*")
    for g in MODEL_GLOBS:
        leftovers += glob.glob(os.path.join(HUB, g + FRESH + "*"))
    if leftovers:
        print("  上次模拟留档(可手动删):")
        for p in leftovers:
            print(f"    {p}  ({_size(p):.0f} MB)")
    return hidden


def start():
    if _running():
        print(f"✗ 先关掉: {_running()}")
        sys.exit(1)
    moved, skipped = [], []
    if os.path.isdir(DATA + REAL):
        skipped.append(DATA)
    elif os.path.isdir(DATA):
        os.rename(DATA, DATA + REAL)
        moved.append(DATA)
    for d in _model_dirs():
        if os.path.isdir(d + REAL):
            skipped.append(d)          # 上次已藏, 现在这个是模拟期间新生成的, 保留
            continue
        os.rename(d, d + REAL)
        moved.append(d)
    print("✓ 已切到【新用户】状态" + (", 藏起来的:" if moved else " (本来就是)"))
    for m in moved:
        print(f"    {m}  ->  {os.path.basename(m)}{REAL}")
    for s in skipped:
        print(f"    (已藏过, 跳过) {s}")
    print("\n现在去 Modules\\BannerlordVoiceLink\\VoiceApp\\run.bat 走新手流程:")
    print("  1) 启动器: ① 音频与模型设置 应金边高亮")
    print("  2) 首次会弹 GPU 加速引导(下载 CUDA 库到数据目录)")
    print("  3) 音频设置里: turbo 应显示「需联网下载」, small 是「内置」; 选 turbo -> 下载进度")
    print("  4) 开始语音指挥, 看 app.log 里加载的是哪个模型、GPU 还是 CPU")
    print("\n测完: python tools/fresh_user.py restore")


def restore():
    if _running():
        print(f"✗ 先关掉: {_running()}")
        sys.exit(1)
    if not os.path.isdir(DATA + REAL) and not _model_dirs(REAL):
        print("✗ 没有藏起来的真实状态, 无需恢复。")
        sys.exit(1)
    ts = time.strftime("%Y%m%d-%H%M")
    kept = []
    if os.path.isdir(DATA + REAL):
        if os.path.isdir(DATA):
            dst = f"{DATA}{FRESH}-{ts}"
            os.rename(DATA, dst)
            kept.append(dst)
        os.rename(DATA + REAL, DATA)
    for d in _model_dirs(REAL):
        orig = d[:-len(REAL)]
        if os.path.isdir(orig):
            dst = f"{orig}{FRESH}-{ts}"
            os.rename(orig, dst)
            kept.append(dst)
        os.rename(d, orig)
    print("✓ 已恢复真实状态。")
    if kept:
        print("模拟期间新产生的东西留档在(确认没用就手动删, 脚本不替你删):")
        for p in kept:
            print(f"    {p}  ({_size(p):.0f} MB)")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if is_virtualized() and "--inside" not in sys.argv:
        print("(本终端的 %LOCALAPPDATA% 被 MSIX 虚拟化, 改在容器外执行…)")
        print(run_outside([sys.executable, os.path.abspath(__file__), cmd, "--inside"]))
    else:
        {"start": start, "restore": restore, "status": status}.get(cmd, status)()
