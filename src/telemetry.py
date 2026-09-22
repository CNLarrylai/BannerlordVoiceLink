# -*- coding: utf-8 -*-
"""使用数据埋点 —— 先只落本地, 上传是另一层(需用户同意 + 收集端, 见 upload 说明)。

记什么(产品问题 -> 事件):
  * 玩家把设置改成了什么: settings_changed {field, old, new}
    (监听模式 / 监听键 / 按住说话键 / 模型 / 运行设备 / 界面语言)
  * 会话概况: session_start {mode, model, lang, version}
不记什么: 录音、识别出的文字、麦克风设备名(可能含个人信息)、任何账号信息。

落地: <日志目录>/events.jsonl, 一行一个事件; "打包日志"会把它一起打进 zip。
匿名安装 ID: 首次调用随机生成(uuid4), 存在数据目录, 不和任何硬件/账号绑定。
"""
import json
import os
import time
import uuid

_MAX_BYTES = 2 << 20          # 本地文件超过 2MB 就轮转成 .1, 不无限长


def _dir():
    from paths import log_dir
    return log_dir()


def events_path():
    return os.path.join(_dir(), "events.jsonl")


def install_id():
    p = os.path.join(os.path.dirname(_dir()), "install_id")
    try:
        with open(p, encoding="utf-8") as f:
            v = f.read().strip()
            if v:
                return v
    except OSError:
        pass
    v = uuid.uuid4().hex
    try:
        with open(p, "w", encoding="utf-8") as f:
            f.write(v)
    except OSError:
        pass
    return v


def track(event, **props):
    """记一个事件。永不抛异常(埋点坏了不能连累主功能)。"""
    try:
        from version import APP_VERSION
        rec = {"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "id": install_id(),
               "v": APP_VERSION, "event": event, **props}
        p = events_path()
        try:
            if os.path.getsize(p) > _MAX_BYTES:
                os.replace(p, p + ".1")
        except OSError:
            pass
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def track_changes(before, after):
    """before/after: {field: value}。只为真正变了的字段各记一条 settings_changed。"""
    for k, new in after.items():
        old = before.get(k)
        if new is not None and new != old:
            track("settings_changed", field=k, old=old, new=new)
