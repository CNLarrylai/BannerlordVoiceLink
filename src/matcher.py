"""意图匹配 —— 把识别到的中文句子解析成 [兵种] + [指令]。

匹配策略: 对词典里每个别名做模糊匹配 (rapidfuzz), 同分时偏向更长
更具体的别名, 避免 "射手" 抢了 "骑射手" 这类子串误判。

防误触 (区分"下指令"和"聊到指令词"), 三层过滤:
  1. 聊天特征词黑名单 —— 句子里有 "比如/如果/指令/识别" 这类元讨论词,
     说明是在"谈论"而不是"下令", 直接忽略。
  2. 指令占比 —— 剔除语气/填充词后, 匹配到的指令词必须占句子的大头。
     真指令短促干脆 ("全军冲锋"≈100%), 聊天句又长又稀 (≈25%)。
  3. 句长上限 —— 剔除填充词后仍然很长的句子按聊天处理。

另外: 只匹配到兵种、没有指令的句子不执行 (半截匹配只会乱切编队)。
"""
import re

from rapidfuzz import fuzz

try:
    from pypinyin import lazy_pinyin
    _HAS_PINYIN = True
except Exception:
    _HAS_PINYIN = False


def _char_py(ch):
    try:
        r = lazy_pinyin(ch)
        return r[0] if r and r[0] else ""
    except Exception:
        return ""


def alias_pinyin(s):
    """整词的无声调拼音串 (逐字, 保证与 text_pinyin 对齐)。"""
    return "".join(_char_py(c) for c in s)


def text_pinyin(s):
    """返回 (拼音串, pos2char): pos2char[i]=拼音串第 i 位对应原文的字下标。"""
    py, pos2char = [], []
    for ci, ch in enumerate(s):
        syl = _char_py(ch)
        pos2char.extend([ci] * len(syl))
        py.append(syl)
    return "".join(py), pos2char

# 标点/空白, 匹配前先剥掉
PUNCT_RE = re.compile(r"[\s,。!?、,.!?…~··:;:;\"'“”‘’()()【】\[\]\-—]+")

# 语气/填充词: 下令时带上不影响判定 ("弓箭手全部给我散开!")
FILLERS = [
    "给我", "全部", "全都", "立刻", "马上", "快点", "现在", "赶紧",
    "兄弟们", "一下", "听着", "所有", "都", "们", "了", "的", "地",
    "啊", "吧", "呀", "哦", "嗯", "呢", "哈", "来", "去", "请", "让",
    "顶住", "上", "冲啊", "杀啊", "快来", "快",   # 战场喊话式填充
]

# 聊天特征词: 出现即视为聊天, 不执行 (讲解/提问/讨论软件时的典型用词)
CHAT_MARKERS = [
    "比如", "如果", "就是", "这种", "这个", "那个", "一种", "一句",
    "指令", "命令", "识别", "检测", "测试", "语音", "说话", "生效",
    "什么", "为什么", "怎么", "可能", "应该", "觉得", "意思", "发现",
    "你会", "你能", "会不会", "能不能", "是不是", "有没有", "然后",
]

# 指令占比下限: 匹配词 / (匹配词 + 剩余杂字)
MIN_COVERAGE = 0.6
# 剩余杂字 <= 这个数就直接放行 (不卡占比)
MAX_FREE_LEFTOVER = 2
# 剔除填充词后的句长上限, 再长就当聊天
MAX_EFFECTIVE_LEN = 16


class Matcher:
    def __init__(self, commands: dict, threshold: int = 70, chat_filter: bool = True,
                 pinyin_match: bool = True, pinyin_threshold: int = 85,
                 group_threshold=None, order_threshold=None):
        self.groups = commands.get("groups", {})
        self.orders = commands.get("orders", {})
        # 兵种(就5个,叫法少)可松一点; 指令(20+,密,多同音)要严, 防乱路由。
        self.group_threshold = 60 if group_threshold is None else group_threshold
        self.order_threshold = threshold if order_threshold is None else order_threshold
        self.chat_filter = chat_filter
        self.pinyin_match = pinyin_match and _HAS_PINYIN
        self.pinyin_threshold = pinyin_threshold           # 指令谐音: 严 (只认同音)
        self.pinyin_group_threshold = max(55, pinyin_threshold - 8)  # 兵种谐音: 松
        # 预算每个别名的拼音, 匹配时不重复计算
        self._alias_py = {}
        if self.pinyin_match:
            for table in (self.groups, self.orders):
                for data in table.values():
                    for al in data.get("aliases", []):
                        if al not in self._alias_py:
                            self._alias_py[al] = alias_pinyin(al)

    @classmethod
    def from_config(cls, commands, control):
        """按 settings 的 control 段建 Matcher (统一读阈值/开关)。"""
        base = control.get("match_threshold", 72)
        return cls(commands, base,
                   control.get("chat_filter", True),
                   control.get("pinyin_match", True),
                   control.get("pinyin_threshold", 85),
                   group_threshold=control.get("group_threshold", 60),
                   order_threshold=control.get("order_threshold", base))

    def _best(self, text, table, text_py="", pos2char=None, pinyin_threshold=None):
        """在 table 里找最匹配的一项 (汉字匹配 + 谐音/拼音兜底)。

        返回 (key, 数据, 分数, 命中的别名, 命中区间(start,end))。
        谐音: 汉字对不上时, 比拼音 ("骑射"vs"起社"同为 qishe) 也能命中,
        专治口音/同音字听岔。谐音分要更高 (pinyin_threshold) 才采纳, 防误触。
        """
        pt = self.pinyin_threshold if pinyin_threshold is None else pinyin_threshold
        best = (None, None, 0, "", (0, 0))
        for key, data in table.items():
            for alias in data.get("aliases", []):
                pos = text.find(alias)
                if pos >= 0:
                    score, span = 100, (pos, pos + len(alias))
                else:
                    a = fuzz.partial_ratio_alignment(alias, text)
                    score, span = a.score, (a.dest_start, a.dest_end)
                # 谐音兜底: 只在汉字明显对不上(<70)时才用, 且只对 >=2 字的别名
                # (单字拼音太短、到处都能贴, 会乱路由), 拼音串也要够长才可信。
                if (self.pinyin_match and score < 70 and len(alias) >= 2
                        and text_py):
                    apy = self._alias_py.get(alias) or alias_pinyin(alias)
                    if apy and len(apy) >= 4:
                        pa = fuzz.partial_ratio_alignment(apy, text_py)
                        if pa.score >= pt and pa.score > score:
                            span = self._map_span(pa.dest_start, pa.dest_end,
                                                  pos2char, len(text))
                            score = pa.score
                if (score, len(alias)) > (best[2], len(best[3])):
                    best = (key, data, score, alias, span)
        return best

    @staticmethod
    def _map_span(s, e, pos2char, n):
        """把拼音串区间映射回原文字符区间。"""
        if not pos2char:
            return (0, n)
        s = pos2char[s] if 0 <= s < len(pos2char) else 0
        e = pos2char[e - 1] + 1 if 0 < e <= len(pos2char) else n
        return (s, e)

    def _strip_fillers(self, text: str) -> str:
        for f in sorted(FILLERS, key=len, reverse=True):
            text = text.replace(f, "")
        return text

    def _coverage(self, clean: str, spans: list) -> dict:
        """第2+3层: 指令占比 + 句长。返回判定细节 (给测试台展示用)。"""
        mask = [False] * len(clean)
        for s, e in spans:
            for i in range(s, min(e, len(clean))):
                mask[i] = True
        matched_len = sum(mask)
        leftover = self._strip_fillers(
            "".join(ch for i, ch in enumerate(clean) if not mask[i])
        )
        info = {
            "matched_len": matched_len,
            "leftover": leftover,
            "coverage": matched_len / max(1, matched_len + len(leftover)),
            "is_chat": False,
            "why": "",
        }
        if matched_len + len(leftover) > MAX_EFFECTIVE_LEN:
            info["is_chat"] = True
            info["why"] = f"剔除填充词后仍有 {matched_len + len(leftover)} 字 (> {MAX_EFFECTIVE_LEN}), 按聊天处理"
        elif len(leftover) <= MAX_FREE_LEFTOVER:
            info["why"] = f"剩余杂字仅 {len(leftover)} 个, 放行"
        elif info["coverage"] < MIN_COVERAGE:
            info["is_chat"] = True
            info["why"] = (
                f"指令占比 {info['coverage']:.0%} < {MIN_COVERAGE:.0%} "
                f"(剩余杂字「{leftover}」太多), 按聊天处理"
            )
        else:
            info["why"] = f"指令占比 {info['coverage']:.0%} ≥ {MIN_COVERAGE:.0%}, 放行"
        return info

    def explain(self, text: str) -> dict:
        """完整判定过程 (测试台/调试用)。result 字段为 None 表示不执行。"""
        trace = {
            "text": text, "clean": "", "chat_marker": None,
            "group": None, "order": None, "coverage": None,
            "result": None, "reason": "",
        }
        if not text:
            trace["reason"] = "空文本"
            return trace
        clean = PUNCT_RE.sub("", text)
        trace["clean"] = clean
        if not clean:
            trace["reason"] = "只有标点/空白"
            return trace

        # 第1层: 聊天特征词
        if self.chat_filter:
            hit = next((m for m in CHAT_MARKERS if m in clean), None)
            if hit:
                trace["chat_marker"] = hit
                trace["reason"] = f"含聊天特征词「{hit}」, 判为聊天"
                return trace

        if self.pinyin_match:
            text_py, pos2char = text_pinyin(clean)
        else:
            text_py, pos2char = "", None
        # 兵种松(叫法少,安全); 指令严(密,多同音,防乱路由)
        g_key, g_data, g_score, g_alias, g_span = self._best(
            clean, self.groups, text_py, pos2char, self.pinyin_group_threshold)
        o_key, o_data, o_score, o_alias, o_span = self._best(
            clean, self.orders, text_py, pos2char, self.pinyin_threshold)
        if g_key:
            trace["group"] = {
                "name": g_key, "alias": g_alias, "score": round(g_score),
                "pass": g_score >= self.group_threshold,
                "select": g_data["key"],
            }
        if o_key:
            trace["order"] = {
                "name": o_key, "alias": o_alias, "score": round(o_score),
                "pass": o_score >= self.order_threshold,
                "keys": o_data["keys"],
            }

        # 必须有"指令"才执行; 只有兵种的半截匹配只会乱切编队, 忽略
        if not o_key or o_score < self.order_threshold:
            trace["reason"] = (
                f"没有匹配到指令动作 (最接近: {o_key} {round(o_score)}分, "
                f"阈值 {self.order_threshold})" if o_key else "没有匹配到任何指令动作"
            )
            return trace

        spans = [o_span]
        group_ok = g_key and g_score >= self.group_threshold
        if group_ok:
            spans.append(g_span)

        # 第2+3层: 指令占比 + 句长
        if self.chat_filter:
            cov = self._coverage(clean, spans)
            trace["coverage"] = cov
            if cov["is_chat"]:
                trace["reason"] = cov["why"]
                return trace
            # 单字指令(冲/杀/停/放)只在"基本就说了这个字"时才算; 句中还有别的杂字,
            # 多半是错听里蹭到的(如"撤锋"里的撤), 不执行, 免得乱发。
            if len(o_alias) == 1 and cov["leftover"]:
                trace["reason"] = (f"指令只命中单字「{o_alias}」, 句中还有"
                                   f"「{cov['leftover']}」, 疑似错听, 不执行")
                return trace

        order = {"name": o_key, "keys": o_data["keys"], "score": o_score}
        group = (
            {"name": g_key, "select": g_data["key"], "score": g_score}
            if group_ok else None
        )
        trace["result"] = {"text": text, "group": group, "order": order}
        trace["reason"] = "执行"
        return trace

    def parse(self, text: str):
        """返回 {text, group, order} 或 None (无指令/判为聊天)。"""
        return self.explain(text)["result"]
