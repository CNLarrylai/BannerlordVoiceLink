# -*- coding: utf-8 -*-
"""监听按键: "轻点一下"判定 + 按键名显示 + 可绑定键校验。

为什么不直接 keyboard.add_hotkey: 按键模式默认键是左 Alt(用户 2026-09-22 定),
  * Alt+Tab / Alt+F4 里的 Alt 不能算一次开关;
  * 骑砍里按住 Alt 看部队标记是常规操作, 按住再松开也不能算;
  * add_hotkey 在按下时触发, 长按还会连发, 一按开关好几次。
所以: 只认"按下 -> 期间没按别的键 -> TAP_MAX_SECS 内松开"为一次轻点, 松开时触发。
"""
import time

TAP_MAX_SECS = 0.5

MODIFIERS = {"alt", "left alt", "right alt", "ctrl", "left ctrl", "right ctrl",
             "shift", "left shift", "right shift", "windows", "left windows",
             "right windows"}


def on_tap(key, callback, kb=None):
    """key 被轻点一下时调 callback。返回取消函数。组合键("ctrl+f12")退回 add_hotkey。"""
    if kb is None:
        import keyboard as kb
    key = (key or "").strip().lower()
    if "+" in key:
        h = kb.add_hotkey(key, callback)
        return lambda: kb.remove_hotkey(h)
    codes = set(kb.key_to_scan_codes(key))
    st = {"down": 0.0, "clean": False}

    def is_key(e):
        if e.scan_code not in codes:
            return False
        name = (e.name or "").lower()
        # 左右 Alt/Ctrl/Shift 扫描码相同, 只能靠事件名分左右
        # 英式/欧式布局的右 Alt 是 AltGr, 事件名 "alt gr"(还会顺带假按一下左 Ctrl)
        if key.startswith("left ") and (name.startswith("right") or "gr" in name):
            return False
        if key.startswith("right ") and not name.startswith("right"):
            return False
        return True

    def hook(e):
        if is_key(e):
            if e.event_type == "down":
                if not st["down"]:                 # 长按的自动连发只记第一次
                    st["down"], st["clean"] = time.time(), True
            else:
                if st["down"] and st["clean"] and time.time() - st["down"] <= TAP_MAX_SECS:
                    callback()
                st["down"] = 0.0
        elif e.event_type == "down" and st["down"]:
            st["clean"] = False                    # 按住期间按了别的键 = 组合键, 不算

    h = kb.hook(hook)
    return lambda: kb.unhook(h)


def pretty(key):
    """"left alt" -> "Left Alt", "caps lock" -> "Caps Lock", "f12" -> "F12"。"""
    return " ".join(w.upper() if len(w) <= 3 and w[:1] == "f" and w[1:].isdigit()
                    else w.capitalize() for w in (key or "").split())


# Tk keysym -> keyboard 库的键名(设置窗口里"按下新按键"用)
_TK = {"alt_l": "left alt", "alt_r": "right alt", "control_l": "left ctrl",
       "control_r": "right ctrl", "shift_l": "left shift", "shift_r": "right shift",
       "caps_lock": "caps lock", "win_l": "left windows", "win_r": "right windows",
       "super_l": "left windows", "super_r": "right windows", "grave": "`",
       "prior": "page up", "next": "page down", "scroll_lock": "scroll lock",
       "pause": "pause", "insert": "insert", "delete": "delete", "home": "home",
       "end": "end", "tab": "tab", "space": "space", "return": "enter",
       "backspace": "backspace", "escape": "esc", "minus": "-", "equal": "=",
       "bracketleft": "[", "bracketright": "]", "backslash": "\\", "semicolon": ";",
       "apostrophe": "'", "comma": ",", "period": ".", "slash": "/"}


def from_tk(keysym):
    k = (keysym or "").lower()
    if k in _TK:
        return _TK[k]
    if len(k) == 1 or (k[:1] == "f" and k[1:].isdigit()):
        return k
    return k.replace("_", " ")


# 不许绑的键: 游戏里离不开的(指令菜单 F1~F9 / 编队 1~9 / Esc / 移动 WASD / 空格 等),
# 以及本程序自己占用的热键。返回 None = 可用, 否则是原因(给 t() 翻译的中文)。
_GAME = {f"f{i}" for i in range(1, 10)} | {str(i) for i in range(10)} | {
    "esc", "w", "a", "s", "d", "space", "enter", "tab"}


def reject_reason(key, taken=()):
    k = (key or "").lower()
    if not k:
        return "没识别到这个键"
    if k in _GAME:
        return "这个键游戏里要用(指令菜单/编队/移动), 换一个"
    if k in {x.lower() for x in taken if x}:
        return "这个键已被本程序其它功能占用"
    return None
