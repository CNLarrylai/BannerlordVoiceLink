"""统一资源/配置路径 —— 源码与打包两种形态都成立。

- 源码运行: 配置就在项目 config/ (可读可写)。
- 打包运行: 包内 _internal/config/ 是只读默认模板; 用户配置放到
  %LOCALAPPDATA%\\BannerlordVoice\\config\\ (可写), 首次运行自动播种。
  这样音频设置/指令词典能写入用户自己的配置, 且软件更新不会覆盖用户改动。
"""
import os
import shutil
import sys

FROZEN = getattr(sys, "frozen", False)
APP_DIRNAME = "BannerlordVoice"
_CONFIG_FILES = ("settings.yaml", "commands.yaml")


def bundle_dir():
    """包内资源根 (打包=_internal; 源码=项目根)。"""
    if FROZEN:
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def user_data_dir():
    if FROZEN:
        return os.path.join(
            os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), APP_DIRNAME)
    return bundle_dir()


def config_dir():
    """返回可读写的配置目录; 打包首次运行时从包内默认配置播种。"""
    if not FROZEN:
        return os.path.join(bundle_dir(), "config")
    d = os.path.join(user_data_dir(), "config")
    os.makedirs(d, exist_ok=True)
    src = os.path.join(bundle_dir(), "config")
    for name in _CONFIG_FILES:
        dst = os.path.join(d, name)
        if not os.path.exists(dst):
            try:
                shutil.copy(os.path.join(src, name), dst)
            except Exception:
                pass
    return d


def config_path(name):
    return os.path.join(config_dir(), name)
