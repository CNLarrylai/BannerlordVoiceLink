# -*- coding: utf-8 -*-
"""配置版本迁移测试: 老用户升级后词典必须刷新, 且保留麦克风/模型/语言选择。"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from paths import refresh_config  # noqa: E402
from version import APP_VERSION  # noqa: E402

SRC = os.path.join(os.path.dirname(__file__), "..", "config")

OLD_SETTINGS = """\
audio:
  device: "麦克风 (NVIDIA Broadcast)"
  samplerate: 16000
stt:
  model: base
  device: auto
  language: en
control:
  match_threshold: 72
"""
OLD_COMMANDS = "groups: {}\norders: {}\n"


def _fresh_dir(with_old=False):
    d = tempfile.mkdtemp(prefix="cfgmig_")
    if with_old:
        with open(os.path.join(d, "settings.yaml"), "w", encoding="utf-8") as f:
            f.write(OLD_SETTINGS)
        with open(os.path.join(d, "commands.yaml"), "w", encoding="utf-8") as f:
            f.write(OLD_COMMANDS)
    return d


def test_first_install_seeds_everything():
    d = _fresh_dir()
    try:
        refresh_config(d, SRC)
        for name in ("settings.yaml", "commands.yaml", "order_tree.yaml"):
            assert os.path.getsize(os.path.join(d, name)) > 100, name
        with open(os.path.join(d, ".bundled_version"), encoding="utf-8") as f:
            assert f.read().strip() == APP_VERSION
        assert not os.path.isdir(os.path.join(d, "backup"))  # 首装无备份
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_stale_config_refreshed_prefs_kept():
    d = _fresh_dir(with_old=True)
    try:
        refresh_config(d, SRC)
        cmds = open(os.path.join(d, "commands.yaml"), encoding="utf-8").read()
        assert "打最近的" in cmds, "老词典没被刷新!"
        st = open(os.path.join(d, "settings.yaml"), encoding="utf-8").read()
        assert 'device: "麦克风 (NVIDIA Broadcast)"' in st, "用户麦克风选择丢了"
        assert "language: en" in st, "用户语言选择丢了"
        assert "model: base" in st, "用户模型选择丢了"
        assert "retry_boost" in st, "新配置项没进来"
        # 旧文件有备份
        bdir = os.path.join(d, "backup", "old")
        assert os.path.exists(os.path.join(bdir, "commands.yaml"))
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_same_version_untouched():
    d = _fresh_dir()
    try:
        refresh_config(d, SRC)
        p = os.path.join(d, "commands.yaml")
        with open(p, "a", encoding="utf-8") as f:
            f.write("# 用户自己的改动\n")
        refresh_config(d, SRC)   # 同版本再跑: 不能覆盖用户改动
        assert "用户自己的改动" in open(p, encoding="utf-8").read()
        assert not os.path.isdir(os.path.join(d, "backup"))
    finally:
        shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8")
        except Exception:
            pass
    fails = 0
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  ✓ {name}")
            except AssertionError as e:
                fails += 1
                print(f"  ✗✗✗ {name}: {e}")
    print(f"\n{'❌ 有失败' if fails else '✓ 配置迁移全部通过'}")
    sys.exit(1 if fails else 0)
