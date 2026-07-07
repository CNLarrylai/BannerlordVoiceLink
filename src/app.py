"""统一入口 —— 按 --mode 分发到各功能。

一个入口的好处: 打包成 exe 后, 启动器用 `app.exe --mode voice` 再拉起自己,
不再依赖外部 python.exe (打包必须这么做)。源码运行同样有效。

  python src/app.py                 # 启动器 Hub (默认)
  python src/app.py --mode voice    # 语音指挥 (发按键)
  python src/app.py --mode listen   # 测试模式 (只听不发)
  python src/app.py --mode audio    # 音频设置
  python src/app.py --mode dict     # 指令词典
"""
import argparse
import os
import sys

# 保证 src 在 path 上 (源码与打包两种形态都成立)
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)


class _Tee:
    """同时写多个流 (控制台 + 日志文件)。源码版黑窗实时看, 文件留存供排错。"""

    def __init__(self, *streams):
        self._streams = [s for s in streams if s is not None]

    def write(self, s):
        for st in self._streams:
            try:
                st.write(s)
                st.flush()
            except Exception:
                pass
        return len(s)

    def flush(self):
        for st in self._streams:
            try:
                st.flush()
            except Exception:
                pass

    def isatty(self):
        return False

    def reconfigure(self, **kw):
        pass


def _setup_stdio():
    """所有形态都把日志写到文件 (源码同时保留黑窗实时输出)。

    - 源码运行: 有控制台 -> Tee(控制台, 文件), 两边都能看。
    - 打包 windowed: 无控制台(stdout=None) -> 只写文件。
    统一日志文件位置见 paths.log_file(), 排错时始终在一处找。
    """
    console_out, console_err = sys.stdout, sys.stderr
    for s in (console_out, console_err):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:
            pass
    logf = None
    try:
        from datetime import datetime
        from paths import log_file
        p = log_file()
        # 简单滚动: 超过 3MB 就备份一份, 防止无限增长。
        try:
            if os.path.exists(p) and os.path.getsize(p) > 3_000_000:
                os.replace(p, p + ".old")
        except Exception:
            pass
        logf = open(p, "a", encoding="utf-8", buffering=1)
        mode = "?"
        for i, a in enumerate(sys.argv):
            if a == "--mode" and i + 1 < len(sys.argv):
                mode = sys.argv[i + 1]
        logf.write(f"\n===== 新会话 [{mode}] "
                   f"{datetime.now():%Y-%m-%d %H:%M:%S} =====\n")
    except Exception:
        logf = None
    if logf is not None:
        sys.stdout = _Tee(console_out, logf)
        sys.stderr = _Tee(console_err, logf)


_setup_stdio()


def main():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--mode", default="launcher")
    args, _ = ap.parse_known_args()   # 其余参数(如 --dry-run)留给各模块自取
    mode = args.mode

    if mode == "launcher":
        from launcher import Launcher
        Launcher().run()
    elif mode == "voice":
        from main import main as voice_main
        voice_main()
    elif mode == "listen":
        from listen import main as listen_main
        listen_main()
    elif mode == "audio":
        from audio_setup import SetupWindow
        SetupWindow().run()
    elif mode == "dict":
        from command_gui import CommandGUI
        CommandGUI().run()
    else:
        print(f"未知模式: {mode}")
        sys.exit(2)


if __name__ == "__main__":
    main()
