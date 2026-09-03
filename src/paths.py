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
_CONFIG_FILES = ("settings.yaml", "commands.yaml", "order_tree.yaml",
                 "calibration.yaml")


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
    """返回可读写的配置目录; 打包版按版本播种/迁移包内默认配置。"""
    if not FROZEN:
        return os.path.join(bundle_dir(), "config")
    d = os.path.join(user_data_dir(), "config")
    os.makedirs(d, exist_ok=True)
    try:
        _seed_fun_packs(d)
        refresh_config(d, os.path.join(bundle_dir(), "config"))
    except Exception:
        # 迁移失败绝不能挡启动: 至少把缺的文件补上
        for name in _CONFIG_FILES:
            dst = os.path.join(d, name)
            if not os.path.exists(dst):
                try:
                    shutil.copy(os.path.join(bundle_dir(), "config", name), dst)
                except Exception:
                    pass
    return d


def _seed_fun_packs(d):
    """播种包内整活包示例到用户配置目录 (只补缺, 永不覆盖 —— 整活包是
    用户自己的定制内容, 跟个人词典同级, 版本更新不许碰)。"""
    src = os.path.join(bundle_dir(), "config", "fun")
    if not os.path.isdir(src):
        return
    dst = os.path.join(d, "fun")
    os.makedirs(dst, exist_ok=True)
    for name in os.listdir(src):
        if name.endswith(".yaml") and not os.path.exists(os.path.join(dst, name)):
            shutil.copy(os.path.join(src, name), os.path.join(dst, name))


# 版本更新时仍保留的用户选择 (其余改动在 backup/ 里可手动找回)
_KEEP_PREFS = (("audio", "device"), ("stt", "model"),
               ("stt", "device"), ("stt", "language"), ("stt", "engine"),
               ("fun", "pack"))


def refresh_config(d, src):
    """按版本播种/迁移用户配置目录。

    没有这个机制的教训: 老包用户升级后 exe 是新的、%LOCALAPPDATA% 里的
    commands.yaml 永远停在旧版 —— 新增说法/指令全不生效, 识别"变差"。
    策略: 版本戳(.bundled_version)不匹配 => 旧文件整体备份到 backup/<旧版本>/,
    覆盖为新包默认, 再把用户的麦克风/模型/语言等选择写回新 settings.yaml。
    """
    from version import APP_VERSION
    # 戳 = 版本号 + 包内配置内容哈希: 只看版本号的教训(2026-09-02) —— 同一 APP_VERSION
    # 下多次开发打包, 词典改了但用户目录副本永不刷新, 测的是老词典还不自知。
    want = _bundle_stamp(src, APP_VERSION)
    stamp_p = os.path.join(d, ".bundled_version")
    stamp = ""
    if os.path.exists(stamp_p):
        with open(stamp_p, encoding="utf-8") as f:
            stamp = f.read().strip()
    if stamp == want:
        for name in _CONFIG_FILES:      # 版本一致: 只补缺
            dst = os.path.join(d, name)
            if not os.path.exists(dst):
                shutil.copy(os.path.join(src, name), dst)
        return

    old_settings = None
    sp = os.path.join(d, "settings.yaml")
    if os.path.exists(sp):
        with open(sp, encoding="utf-8") as f:
            old_settings = f.read()

    # 备份旧配置 (首次安装无旧文件, 自动跳过)
    bdir = os.path.join(d, "backup", stamp or "old")
    for name in _CONFIG_FILES:
        dst = os.path.join(d, name)
        if os.path.exists(dst):
            os.makedirs(bdir, exist_ok=True)
            shutil.copy(dst, os.path.join(bdir, name))

    for name in _CONFIG_FILES:
        if os.path.exists(os.path.join(src, name)):
            shutil.copy(os.path.join(src, name), os.path.join(d, name))

    if old_settings:
        _reapply_prefs(sp, old_settings)
    with open(stamp_p, "w", encoding="utf-8") as f:
        f.write(want)


def _bundle_stamp(src, version):
    """包内配置的身份: 版本号-内容哈希前8位 (任一默认配置文件变了就换戳)。"""
    import hashlib
    h = hashlib.sha1()
    for name in _CONFIG_FILES:
        p = os.path.join(src, name)
        if os.path.exists(p):
            with open(p, "rb") as f:
                h.update(f.read())
    return f"{version}-{h.hexdigest()[:8]}"


# 历史默认值: 这些不是"用户的选择", 而是老版本播下来的默认。迁移时若发现
# 用户的值正好等于某个历史默认, 说明他从没主动改过 -> 交还给新版默认(auto),
# 否则老用户永远被钉在旧模型上, 后续的默认升级对他们完全无效(2026-08 实测:
# 老配置 model: base 让 0.9.0 的分档逻辑形同虚设)。
_STALE_DEFAULTS = {("stt", "model"): {"base", "auto"}}


def _reapply_prefs(new_settings_path, old_text):
    """把旧 settings.yaml 里的用户选择(白名单)写回新模板。

    例外见 _STALE_DEFAULTS: 等于历史默认的值不算"用户选择", 不写回。
    """
    import re
    prefs = {}
    section = None
    for line in old_text.splitlines():
        if re.match(r"^\S", line):
            section = line.split(":")[0]
        m = re.match(r"^\s+(\w+)\s*:\s*(.+?)\s*$", line)
        if m and (section, m.group(1)) in _KEEP_PREFS:
            key, val = (section, m.group(1)), m.group(2).strip()
            if val.strip('"\'') in _STALE_DEFAULTS.get(key, ()):
                continue      # 陈年默认值 -> 让新版默认接管
            prefs[key] = m.group(2)
    if not prefs:
        return
    with open(new_settings_path, encoding="utf-8") as f:
        lines = f.readlines()
    section = None
    for i, line in enumerate(lines):
        if re.match(r"^\S", line):
            section = line.split(":")[0]
        m = re.match(r"^(\s+)(\w+)(\s*:).*$", line)
        if m and (section, m.group(2)) in prefs:
            lines[i] = f"{m.group(1)}{m.group(2)}: {prefs[(section, m.group(2))]}\n"
    with open(new_settings_path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def config_path(name):
    return os.path.join(config_dir(), name)


def log_dir():
    # 日志统一放到 %LOCALAPPDATA%\BannerlordVoice\logs (源码/打包都是同一处,
    # 方便"查看日志"按钮和排错时始终在一个地方找)。
    d = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                     APP_DIRNAME, "logs")
    os.makedirs(d, exist_ok=True)
    return d


def log_file():
    return os.path.join(log_dir(), "app.log")
