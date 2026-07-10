# -*- coding: utf-8 -*-
"""词典加载 —— 基础(commands.yaml) + 个人(user_aliases.yaml) + 整活包 合并。

个人词典 = 校准模式学到的"你的稳定错听" + 你手动加的说法。
整活包 = config/fun/<包名>.yaml, 直播搞怪用的猎奇说法(爸爸打我→冲锋),
按 settings.yaml 的 fun.pack 单独激活, 可做多个定制版本随打赏切换。
单独存放的原因: 版本更新会刷新 commands.yaml(见 paths.refresh_config),
个人词典/整活包绝不能被冲掉 —— 前者是发音适配层, 后者是节目效果层。
"""
import os

import yaml

from paths import config_path

USER_FILE = "user_aliases.yaml"
FUN_DIR = "fun"


def _merge_aliases(base, extra_by_key, src=""):
    """把 {命令key: {aliases/en 或 直接列表}} 追加进 base (只加不覆盖不删)。"""
    for sec in ("groups", "orders"):
        for key, extra in (extra_by_key.get(sec) or {}).items():
            node = (base.get(sec) or {}).get(key)
            if node is None:
                if src:
                    print(f"[词典] ⚠ {src}: 未知命令 {sec}.{key}, 跳过")
                continue
            if isinstance(extra, list):      # 整活包简写: key: [说法, ...]
                extra = {"aliases": extra}
            for field in ("aliases", "en"):
                add = extra.get(field) or []
                cur = node.setdefault(field, [])
                for a in add:
                    if a not in cur:
                        cur.append(a)


def load_commands():
    """基础 + 个人词典 + 激活的整活包, 合并后的 commands (所有消费方统一入口)。"""
    with open(config_path("commands.yaml"), encoding="utf-8") as f:
        base = yaml.safe_load(f)
    _merge_aliases(base, load_user())
    pack = active_fun_pack()
    if pack:
        data = load_fun_pack(pack)
        if data is None:
            print(f"[词典] ⚠ 整活包「{pack}」不存在 (config/{FUN_DIR}/), 忽略")
        else:
            _merge_aliases(base, data, src=f"整活包{pack}")
    return base


# ---------- 整活包 ----------

def fun_dir():
    d = os.path.join(os.path.dirname(config_path("commands.yaml")), FUN_DIR)
    os.makedirs(d, exist_ok=True)
    return d


def list_fun_packs():
    """可用整活包名列表 (不带 .yaml)。"""
    try:
        return sorted(f[:-5] for f in os.listdir(fun_dir())
                      if f.endswith(".yaml"))
    except OSError:
        return []


def active_fun_pack():
    """settings.yaml 里激活的包名; 未配置/关闭返回 None。"""
    try:
        with open(config_path("settings.yaml"), encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        p = (cfg.get("fun") or {}).get("pack")
        return str(p) if p else None
    except Exception:
        return None


def load_fun_pack(name):
    """读一个整活包; 不存在/坏文件返回 None。"""
    p = os.path.join(fun_dir(), f"{name}.yaml")
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return None


def load_user():
    p = config_path(USER_FILE)
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def add_user_alias(section, key, alias, lang="zh"):
    """把一条说法写进个人词典。返回 True=新增, False=已存在。"""
    field = "en" if lang == "en" else "aliases"
    user = load_user()
    node = user.setdefault(section, {}).setdefault(key, {})
    arr = node.setdefault(field, [])
    if alias in arr:
        return False
    arr.append(alias)
    with open(config_path(USER_FILE), "w", encoding="utf-8") as f:
        f.write("# 个人词典 —— 校准模式学到的你的说法/错听 + 手动添加。\n"
                "# 软件更新不会覆盖这个文件。\n")
        yaml.safe_dump(user, f, allow_unicode=True, sort_keys=False)
    return True
