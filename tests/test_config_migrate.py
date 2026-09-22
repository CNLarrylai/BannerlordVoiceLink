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
            assert f.read().strip().startswith(APP_VERSION)
        assert not os.path.isdir(os.path.join(d, "backup"))  # 首装无备份
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_stale_config_refreshed_prefs_kept():
    d = _fresh_dir(with_old=True)
    try:
        refresh_config(d, SRC)
        cmds = open(os.path.join(d, "commands.yaml"), encoding="utf-8").read()
        assert "打他们" in cmds, "老词典没被刷新!"   # charge 新增别名, 应在刷新后出现
        st = open(os.path.join(d, "settings.yaml"), encoding="utf-8").read()
        assert 'device: "麦克风 (NVIDIA Broadcast)"' in st, "用户麦克风选择丢了"
        assert "language: en" in st, "用户语言选择丢了"
        assert "retry_boost" in st, "新配置项没进来"
        # model: base 是老版本播下来的历史默认, 不是用户主动选的 -> 不写回,
        # 让新模板的默认接管(打包版模板是 auto; 本机模板是开发者自己的值)。
        # 否则老用户永远被钉在旧模型上, 后续默认升级形同虚设。
        assert "model: base" not in st, "陈年默认 base 又被写回来了"
        # 旧文件有备份
        bdir = os.path.join(d, "backup", "old")
        assert os.path.exists(os.path.join(bdir, "commands.yaml"))
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_real_model_choice_is_kept():
    """对照组: 用户主动选的非默认模型(medium)必须原样保留 —— 不能一刀切。"""
    d = _fresh_dir(with_old=True)
    try:
        p = os.path.join(d, "settings.yaml")
        txt = open(p, encoding="utf-8").read().replace("model: base",
                                                       "model: medium")
        with open(p, "w", encoding="utf-8") as f:
            f.write(txt)
        refresh_config(d, SRC)
        st = open(p, encoding="utf-8").read()
        assert "model: medium" in st, "用户主动选的模型被覆盖了!"
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


def test_same_version_new_dictionary_refreshes():
    """同一 APP_VERSION 下包内词典改了 => 必须刷新(戳含内容哈希)。
    教训: 开发期多次打包版本号不变, 用户目录词典永不更新, 测的是老词典。"""
    import tempfile
    d = _fresh_dir()
    src2 = tempfile.mkdtemp(prefix="bundle_")
    try:
        refresh_config(d, SRC)
        for name in os.listdir(SRC):
            if name.endswith(".yaml"):
                shutil.copy(os.path.join(SRC, name), os.path.join(src2, name))
        with open(os.path.join(src2, "commands.yaml"), "a", encoding="utf-8") as f:
            f.write("# 新版词典标记 NEW_ALIAS_MARKER" + chr(10))
        refresh_config(d, src2)   # 版本没变, 内容变了 -> 刷新
        cmds = open(os.path.join(d, "commands.yaml"), encoding="utf-8").read()
        assert "NEW_ALIAS_MARKER" in cmds, "同版本词典改动没刷进用户目录"
        assert os.path.isdir(os.path.join(d, "backup")), "刷新前应备份旧配置"
    finally:
        shutil.rmtree(d, ignore_errors=True)
        shutil.rmtree(src2, ignore_errors=True)


def test_first_install_follows_system_language():
    """首装: 界面/识别语言跟系统(中文->zh, 其它->en); 升级: 用户选过的语言不被探测覆盖。"""
    import paths
    orig = paths.system_lang
    try:
        for sys_lang in ("en", "zh"):
            paths.system_lang = lambda s=sys_lang: s
            d = _fresh_dir()
            try:
                refresh_config(d, SRC)
                st = open(os.path.join(d, "settings.yaml"), encoding="utf-8").read()
                assert f"language: {sys_lang}" in st, (sys_lang, st[:400])
            finally:
                shutil.rmtree(d, ignore_errors=True)
        # 老用户 settings 里 language: en, 系统是中文 -> 仍是 en
        paths.system_lang = lambda: "zh"
        d = _fresh_dir(with_old=True)
        try:
            refresh_config(d, SRC)
            st = open(os.path.join(d, "settings.yaml"), encoding="utf-8").read()
            assert "language: en" in st, "升级时用户语言被系统探测覆盖了"
        finally:
            shutil.rmtree(d, ignore_errors=True)
    finally:
        paths.system_lang = orig
    assert paths.system_lang() in ("zh", "en")


def test_listen_mode_and_keys_survive_upgrade():
    """监听模式/键位是用户选择, 升级保留; 但旧默认 F12(0.9.8 前一直监听下的静音键)
    不算选择, 让新默认左 Alt 接管。"""
    import re
    for old_key, want in (('"f12"', '"left alt"'), ('"right ctrl"', '"right ctrl"')):
        d = _fresh_dir(with_old=True)
        try:
            p = os.path.join(d, "settings.yaml")
            txt = open(p, encoding="utf-8").read().replace(
                "control:\n", "control:\n  mode: toggle\n  push_to_talk_key: \"v\"\n"
                f"  listen_toggle_key: {old_key}\n")
            with open(p, "w", encoding="utf-8") as f:
                f.write(txt)
            refresh_config(d, SRC)
            st = open(p, encoding="utf-8").read()
            assert re.search(r"^  mode: toggle$", st, re.M), "监听模式丢了"
            assert 'push_to_talk_key: "v"' in st, "按住说话键丢了"
            assert f"listen_toggle_key: {want}" in st, (old_key, "->", want)
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
