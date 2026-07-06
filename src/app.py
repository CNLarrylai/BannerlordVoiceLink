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

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass


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
