# -*- coding: utf-8 -*-
"""相对站位 / 位置微调 —— 语法 `A(队伍) 去 B(队伍) 的 C(方位) [D(距离)]`。

路线图第 3 条(2026-09-03 用户定)。两种省略形式:
  - B 省略 = 相对 A 自己: "骑兵往右 20 米" / "Cavalry, move 20 meters to the right"
    —— 必须带距离, 否则"往后退"这类归词典里的后退指令(不能抢)。
  - 有 B: "骑兵去弓箭手右边" / "Cavalry, go to the right of the archers"
    —— 方位以 B 朝敌方向为准(不是屏幕), 默认 20 米。

为什么不走通用 matcher: 中文方位词在目标之后("去弓箭手右边"), 通用匹配只认
"动词在前、目标在后"。这里用带占位的正则先抠出 A/B/方位/距离, 兵种识别仍复用
matcher(拼音/模糊/个人词典全生效)。在通用匹配之前调用; 解析不出返回 None,
一切照旧 —— 零影响既有指令(回归锁定于 tests/test_relpos.py)。
"""
import re

CLASSES = ("infantry", "archers", "cavalry", "horse_archers")
DEFAULT_DIST = 20
MAX_DIST = 200

_SIDE_ZH = {
    "左手边": "left", "左边": "left", "左侧": "left", "左面": "left", "左": "left",
    "右手边": "right", "右边": "right", "右侧": "right", "右面": "right", "右": "right",
    "前面": "front", "前边": "front", "前方": "front", "前": "front",
    "后面": "back", "后边": "back", "后方": "back", "后": "back",
}
_SIDE_ZH_RE = "|".join(sorted(_SIDE_ZH, key=len, reverse=True))
_NUM_ZH = "零一二两三四五六七八九十百"
_NUM_RE = rf"[{_NUM_ZH}\d]+"

# 有 B: A 去 B [的] 方位 [D 米]
_ZH_B = re.compile(
    rf"^(?P<a>.{{0,8}}?)(去|到|站到|移到|移动到|走到|开到|靠到|跑到)"
    rf"(?P<b>.{{1,8}}?)的?(?P<side>{_SIDE_ZH_RE})(?P<d>{_NUM_RE})?(米|步|米远)?$")
# 无 B, 相对自己, 必须带距离: A [往/向] 方位 [动词] D 米
_ZH_SELF = re.compile(
    rf"^(?P<a>.{{0,8}}?)(往|向|朝)?(?P<side>{_SIDE_ZH_RE})(移动|移|走|退|挪|靠|站|去|进)?"
    rf"(?P<d>{_NUM_RE})(米|步|米远)$")

_SIDE_EN = {"left": "left", "right": "right", "front": "front", "forward": "front",
            "ahead": "front", "behind": "back", "back": "back", "rear": "back",
            "backward": "back", "backwards": "back"}
_UNIT = r"(?:m|meters|metres|meter|metre|paces|yards|steps)"
_EN_B = re.compile(
    r"^(?P<a>.*?)\b(?:go|move|get|ride|shift|head|reposition)\b\s*(?:over\s+)?(?:to\s+)?(?:the\s+)?"
    r"(?:in\s+)?(?P<side>left|right|front|behind|back|rear)(?:\s+side)?(?:\s+of)?\s+(?:the\s+)?"
    r"(?P<b>[a-z ]+?)(?:\s*,?\s*(?P<d>\d+)\s*" + _UNIT + r")?\s*$")
_EN_SELF_1 = re.compile(   # A move 20 meters to the right
    r"^(?P<a>.*?)\b(?:go|move|shift|step|fall|pull)?\s*(?:back\s+)?(?P<d>\d+)\s*" + _UNIT +
    r"\s*(?:to\s+the\s+|to\s+|on\s+the\s+)?(?P<side>left|right|forward|ahead|back|backward|backwards)\s*$")
_EN_SELF_2 = re.compile(   # A move (to the) right 20 meters / A fall back 30 meters / A right by 20 m
    r"^(?P<a>.*?)\b(?:go|move|shift|step|fall|pull|advance)?\s*(?:to\s+the\s+|to\s+)?(?P<side>left|right|forward|ahead|back|backward|backwards)"
    r"\s*(?:by\s+)?(?P<d>\d+)\s*" + _UNIT + r"\s*$")


def _zh_num(s):
    if not s:
        return None
    if s.isdigit():
        return int(s)
    digits = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
              "六": 6, "七": 7, "八": 8, "九": 9}
    total, cur = 0, 0
    for ch in s:
        if ch == "百":
            total += (cur or 1) * 100
            cur = 0
        elif ch == "十":
            total += (cur or 1) * 10
            cur = 0
        elif ch in digits:
            cur = digits[ch]
        elif ch.isdigit():
            cur = cur * 10 + int(ch)
        else:
            return None
    return total + cur


def _group(matcher, seg, allow_all=False):
    """片段里的兵种(复用 matcher: 拼音/模糊/个人词典)。没有或没过线 -> None。"""
    seg = seg.strip(" ,，、。!！")
    if not seg:
        return None
    g = matcher.explain(seg).get("group")
    if not g or not g["pass"]:
        return None
    name = g["name"]
    # 错听形(如"功箭手")单独看时可能被拼音蹭到伪兵种 archers_left(别名更长赢
    # tiebreak); 站位只关心兵种本身, 半队归回其兵种
    for suf in ("_left", "_right"):
        if name.endswith(suf) and name[:-len(suf)] in CLASSES:
            name = name[:-len(suf)]
    if name in CLASSES or (allow_all and name == "all"):
        return name
    return None


def parse(text, matcher, lang="zh"):
    """-> {"group","ward","side","dist"} 或 None。ward=None 表示相对自己。"""
    if not text:
        return None
    if lang == "en":
        return _parse_en(text.lower(), matcher)
    return _parse_zh(matcher._clean(text), matcher)


def _finish(matcher, a_seg, b_seg, side, d_raw, lang):
    dist = _zh_num(d_raw) if lang == "zh" else (int(d_raw) if d_raw else None)
    if d_raw and (dist is None or dist <= 0):
        return None
    if dist is not None and dist > MAX_DIST:
        return None
    a = _group(matcher, a_seg, allow_all=False)
    if not a:
        return None          # 没说清哪支队 -> 不接(让通用匹配/聊天过滤处理)
    ward = None
    if b_seg is not None:
        ward = _group(matcher, b_seg)
        if not ward or ward == a:
            return None
    if ward is None and dist is None:
        return None          # 相对自己必须带距离(否则是词典里的后退/前进)
    return {"group": a, "ward": ward, "side": side,
            "dist": dist if dist is not None else DEFAULT_DIST}


def _parse_zh(clean, matcher):
    m = _ZH_B.match(clean)
    if m:
        r = _finish(matcher, m.group("a"), m.group("b"), _SIDE_ZH[m.group("side")],
                    m.group("d"), "zh")
        if r:
            return r
    m = _ZH_SELF.match(clean)
    if m:
        return _finish(matcher, m.group("a"), None, _SIDE_ZH[m.group("side")],
                       m.group("d"), "zh")
    return None


def _parse_en(low, matcher):
    low = re.sub(r"[^a-z0-9 ]", " ", low)
    low = re.sub(r"\s+", " ", low).strip()
    m = _EN_B.match(low)
    if m:
        r = _finish(matcher, m.group("a"), m.group("b"), _SIDE_EN[m.group("side")],
                    m.group("d"), "en")
        if r:
            return r
    for pat in (_EN_SELF_1, _EN_SELF_2):
        m = pat.match(low)
        if m:
            r = _finish(matcher, m.group("a"), None, _SIDE_EN[m.group("side")],
                        m.group("d"), "en")
            if r:
                return r
    return None


def describe(rel, commands, lang="zh"):
    """浮层/日志用的一句话。"""
    def disp(key):
        d = commands["groups"][key]
        al = d.get("en") if lang == "en" else d.get("aliases")
        return al[0] if al else key
    side_zh = {"left": "左边", "right": "右边", "front": "前面", "back": "后面"}
    side_en = {"left": "left of", "right": "right of", "front": "in front of", "back": "behind"}
    if lang == "en":
        where = (f"{side_en[rel['side']]} the {disp(rel['ward'])}" if rel["ward"]
                 else {"left": "to the left", "right": "to the right",
                       "front": "forward", "back": "back"}[rel["side"]])
        return f"{disp(rel['group'])} → move {rel['dist']}m {where}"
    where = (f"{disp(rel['ward'])}{side_zh[rel['side']]}" if rel["ward"]
             else f"往{side_zh[rel['side']][0]}")
    return f"{disp(rel['group'])} → 到{where} {rel['dist']}米"
