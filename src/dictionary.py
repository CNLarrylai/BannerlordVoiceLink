# -*- coding: utf-8 -*-
"""词典加载 —— 基础词典(commands.yaml) + 个人词典(user_aliases.yaml) 合并。

个人词典 = 校准模式学到的"你的稳定错听" + 你手动加的说法。
单独存放的原因: 版本更新会刷新 commands.yaml(见 paths.refresh_config),
个人词典绝不能被冲掉 —— 它是每个玩家自己的发音适配层。
"""
import os

import yaml

from paths import config_path

USER_FILE = "user_aliases.yaml"


def load_commands():
    """基础词典 + 个人词典合并后的 commands dict (所有消费方统一入口)。"""
    with open(config_path("commands.yaml"), encoding="utf-8") as f:
        base = yaml.safe_load(f)
    user = load_user()
    for sec in ("groups", "orders"):
        for key, extra in (user.get(sec) or {}).items():
            node = (base.get(sec) or {}).get(key)
            if node is None:
                continue
            for field in ("aliases", "en"):
                add = extra.get(field) or []
                cur = node.setdefault(field, [])
                for a in add:
                    if a not in cur:
                        cur.append(a)
    return base


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
