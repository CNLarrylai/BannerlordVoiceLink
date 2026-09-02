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

# 英文模式: 占比/杂字/句长全部按"词"算, 不按字母 —— 中文一个字≈一个音节,
# 英文一个词才是同量级单位。曾按字母算: "or unit charge"(All 被听成 or)
# 剩 "orunit" 6 个字母被当 6 个汉字的闲聊, 连听对的 charge 都一起丢了。
EN_FILLERS = {"please", "now", "just", "lets", "let", "us", "okay", "ok",
              "alright", "come", "on", "go", "right", "hey", "guys", "and",
              "the", "your", "you", "all", "men", "boys", "soldiers"}
EN_CHAT_MARKERS = []          # 英文暂不做讨论词黑名单, 靠占比过滤
EN_MAX_WORDS = 9              # 去掉填充词后超过这么多词 => 当聊天
EN_MAX_FREE_LEFTOVER = 1      # 剩 1 个没解释的词直接放行(≈中文的 2 个字)
EN_MAX_EFFECTIVE_LEN = 42     # 仅作兜底(字符), 主判定看词数


# 否定字: 别名以这些字开头且对齐时把它们丢掉 => 匹到的是反义(别开火→开火)
NEG_PREFIX = set("别不停收住甭莫")


def _mostly_inside(inner, outer):
    """inner 区间是否大部分落在 outer 内 (>=60% 重叠)。用于判"寄生"子串匹配。"""
    a, b = inner
    if b <= a:
        return False
    ov = max(0, min(b, outer[1]) - max(a, outer[0]))
    return ov / (b - a) >= 0.6


class Matcher:
    def __init__(self, commands: dict, threshold: int = 70, chat_filter: bool = True,
                 pinyin_match: bool = True, pinyin_threshold: int = 85,
                 group_threshold=None, order_threshold=None, lang: str = "zh"):
        self.lang = lang
        self.groups = commands.get("groups", {})
        self.orders = commands.get("orders", {})
        # 兵种(就5个,叫法少)可松一点; 指令(20+,密,多同音)要严, 防乱路由。
        self.group_threshold = 60 if group_threshold is None else group_threshold
        self.order_threshold = threshold if order_threshold is None else order_threshold
        if lang == "en":
            # 英文单词字母重合多(archer/charge)、且 Whisper 英文很准 -> 靠高阈值近精确匹配
            self.group_threshold = 78
            self.order_threshold = 80
        self.chat_filter = chat_filter
        # 谐音只对中文有意义
        self.pinyin_match = (lang == "zh") and pinyin_match and _HAS_PINYIN
        self.pinyin_threshold = pinyin_threshold
        self.pinyin_group_threshold = max(55, pinyin_threshold - 8)
        # 语言相关: 填充词 / 讨论词 / 句长上限
        self.fillers = EN_FILLERS if lang == "en" else FILLERS
        self.chat_markers = EN_CHAT_MARKERS if lang == "en" else CHAT_MARKERS
        self.max_eff_len = EN_MAX_EFFECTIVE_LEN if lang == "en" else MAX_EFFECTIVE_LEN
        # 预算别名的"清洗形"和拼音, 匹配时不重复算
        self._clean_map = {}
        self._alias_py = {}
        for table in (self.groups, self.orders):
            for data in table.values():
                for al in self._aliases(data):
                    if al not in self._clean_map:
                        self._clean_map[al] = self._clean(al)
                    if self.pinyin_match and al not in self._alias_py:
                        self._alias_py[al] = alias_pinyin(al)

    def _aliases(self, data):
        return data.get("en", []) if self.lang == "en" else data.get("aliases", [])

    def _clean(self, text):
        """去噪, 白名单式: 只留汉字/数字/字母, 其余(标点/空格)一律去掉。

        白名单比黑名单(PUNCT_RE)稳: Whisper 会在连读里塞各种标点(全角冒号、
        顿号…), 一个个列举必漏 —— 曾漏全角冒号'：', 把'弓骑兵：冲锋'的冒号
        算进杂字, 指令占比被拉低误判成聊天。只保留会用到的字符, 从此免疫。
        """
        if self.lang == "en":
            return re.sub(r"[^a-z0-9]", "", text.lower())
        # 一-鿿 常用汉字 + 㐀-䶿 扩展A + 字母数字
        return re.sub(r"[^一-鿿㐀-䶿0-9a-zA-Z]", "", text)

    @classmethod
    def from_config(cls, commands, control, lang="zh"):
        """按 settings 的 control 段建 Matcher (统一读阈值/开关)。"""
        base = control.get("match_threshold", 72)
        return cls(commands, base,
                   control.get("chat_filter", True),
                   control.get("pinyin_match", True),
                   control.get("pinyin_threshold", 85),
                   group_threshold=control.get("group_threshold", 60),
                   order_threshold=control.get("order_threshold", base),
                   lang=lang)

    def _best(self, text, table, text_py="", pos2char=None, pinyin_threshold=None,
              bonus_map=None):
        """在 table 里找最匹配的一项 (汉字匹配 + 谐音/拼音兜底)。

        返回 (key, 数据, 分数, 命中的别名, 命中区间(start,end))。
        谐音: 汉字对不上时, 比拼音 ("骑射"vs"起社"同为 qishe) 也能命中,
        专治口音/同音字听岔。谐音分要更高 (pinyin_threshold) 才采纳, 防误触。
        bonus_map: {key: 加分} —— 重试助推用, 只给指定候选定向加分
        (用户重说一遍时放大上次差点命中的那几条, 见 retry.py)。
        """
        pt = self.pinyin_threshold if pinyin_threshold is None else pinyin_threshold
        best = (None, None, 0, "", (0, 0))
        best_cmp = (0, False, False, 0)  # (分数, 解释整句, 完整出现, 别名长度)
        for key, data in table.items():
            for alias in self._aliases(data):
                ca = self._clean_map.get(alias) or self._clean(alias)
                if not ca:
                    continue
                pos = text.find(ca)
                # 别名(>=2字)整体出现在输入里 —— 用于 tiebreak 压过"含它的更长别名"。
                # 限>=2字: 单字精确("冲"在"冲缝"里)本就弱, 不该压过拼音匹配的"冲锋"。
                # 例外: 整句就是这个别名(ca==text) —— 用户只喊了"冲", 必须赢
                # "跟我冲"这类把单字藏在肚子里的更长别名。
                exact = pos >= 0 and (len(ca) >= 2 or ca == text)
                if pos >= 0:
                    score, span = 100, (pos, pos + len(ca))
                    neg_drop = False
                else:
                    a = fuzz.partial_ratio_alignment(ca, text)
                    score, span = a.score, (a.dest_start, a.dest_end)
                    neg_drop = bool(NEG_PREFIX & set(ca[:a.src_start]))
                    # 英文: 整句比别名短时 partial_ratio 是"短串滑进长串", 天然
                    # 虚高 —— 噪音吐出的 "Or." 在 scatter formation 里能蹭 100。
                    # 按长度比打折: or(2)/scatterformation(16) -> 12 分。
                    if self.lang == "en" and len(text) < len(ca):
                        score = score * len(text) / len(ca)
                # 谐音兜底(仅中文): 别名>=2字时比拼音, 取更高分。
                # 不设"汉字分低才比"的门槛 —— 曾因门槛(<70)把"三角镇"vs"三角阵"
                # (汉字80, 拼音100)关在门外, 反让"交战"(汉字低→进兜底, 拼音87.5)
                # 超车。真命中必须也有资格走拼音。
                if (self.pinyin_match and score < 100 and len(ca) >= 2 and text_py):
                    apy = self._alias_py.get(alias) or alias_pinyin(alias)
                    # 整句拼音明显比别名拼音短 => 不可能说的是这个别名, 跳过。
                    # (防"方"fang 在"结盾防御"jiedunFANGyu 里滑窗蹭出100分)
                    if apy and len(apy) >= 4 and len(text_py) * 1.5 >= len(apy):
                        pa = fuzz.partial_ratio_alignment(apy, text_py)
                        if pa.score >= pt and pa.score > score:
                            span = self._map_span(pa.dest_start, pa.dest_end,
                                                  pos2char, len(text))
                            score = pa.score
                            neg_drop = bool(
                                NEG_PREFIX & self._py_prefix_chars(
                                    alias, pa.src_start))
                # 否定前缀守卫: 对齐只盖住别名后半截、被丢掉的前缀含否定字
                # ("开货"滑进"别开火"只匹到"开火") => 语义反转(想开火变停火),
                # 这个候选整个作废。反例"别开火"完整出现时 pos>=0 不受影响。
                if neg_drop:
                    continue
                if bonus_map:
                    score += bonus_map.get(key, 0)
                # tiebreak: 分数 > 解释整句 > 别名完整出现 > 更长。
                # "解释整句"(覆盖全文)优先于精确: "停止蛇己"(=停止射击的平翘舌
                # 错听)整句拼音与"停止射击"全同, 不能输给只覆盖一半的字面子串
                # "停止" —— 否则喊停止射击会执行成立定。
                # 只认"整句"不认"更长": 部分覆盖不许压精确 —— "步兵进攻骑兵"里
                # "弓骑兵"拼音正好藏在"进攻骑兵"(jinGONGQIBING)中覆盖4字,
                # 若按覆盖长度比会抢走"步兵"。
                # 精确仍防"前进"被含它的"列队前进"抢(两者都整句时精确赢)。
                full = (span[1] - span[0]) >= len(text)
                cand = (score, full, exact, len(ca))
                better = cand > best_cmp
                # 同为满分且一方区间真包含另一方: 解释更多文本的同音整词赢。
                # 专治同音字替换造出的精确子串陷阱: "弓骑兵"听成"功骑兵",
                # 拼音满分的"弓骑兵"(盖3字)不能输给字面藏在里面的"骑兵"(2字),
                # 否则"进攻对方弓骑兵"会变成打骑兵。反向包含时则守住现任。
                if cand[0] == best_cmp[0] and cand[0] >= 100 and best[0]:
                    a, b = span, best[4]
                    if (a[0] <= b[0] and a[1] >= b[1]
                            and a[1] - a[0] > b[1] - b[0]):
                        better = True
                    elif (b[0] <= a[0] and b[1] >= a[1]
                            and b[1] - b[0] > a[1] - a[0]):
                        better = False
                if better:
                    best_cmp = cand
                    best = (key, data, score, alias, span)
        return best

    @staticmethod
    def _py_prefix_chars(alias, py_start):
        """别名拼音串前 py_start 位覆盖不到的开头几个字 (整字被对齐丢掉的)。"""
        out = set()
        acc = 0
        for ch in alias:
            ln = len(_char_py(ch))
            if ln and acc + ln <= py_start:
                out.add(ch)
                acc += ln
            else:
                break
        return out

    @staticmethod
    def _map_span(s, e, pos2char, n):
        """把拼音串区间映射回原文字符区间。"""
        if not pos2char:
            return (0, n)
        s = pos2char[s] if 0 <= s < len(pos2char) else 0
        e = pos2char[e - 1] + 1 if 0 < e <= len(pos2char) else n
        return (s, e)

    def _strip_fillers(self, text: str) -> str:
        for f in sorted(self.fillers, key=len, reverse=True):
            text = text.replace(f, "")
        return text

    def _coverage_en(self, words: list, spans: list) -> dict:
        """英文版第2+3层: 按词算。词被任一命中区间覆盖 >=50% 字母即算解释了。"""
        starts, off = [], 0
        for w in words:
            starts.append(off)
            off += len(w)
        matched, leftover = 0, []
        for w, st in zip(words, starts):
            ed = st + len(w)
            ov = max((max(0, min(ed, e) - max(st, s)) for s, e in spans),
                     default=0)
            if ov * 2 >= len(w):
                matched += 1
            elif w not in EN_FILLERS:
                leftover.append(w)
        info = {
            "matched_len": matched,
            "leftover": " ".join(leftover),
            "coverage": matched / max(1, matched + len(leftover)),
            "is_chat": False,
            "why": "",
        }
        total = matched + len(leftover)
        if total > EN_MAX_WORDS:
            info["is_chat"] = True
            info["why"] = f"剔除填充词后仍有 {total} 个词 (> {EN_MAX_WORDS}), 按聊天处理"
        elif len(leftover) <= EN_MAX_FREE_LEFTOVER:
            info["why"] = f"剩余杂词仅 {len(leftover)} 个, 放行"
        elif info["coverage"] < MIN_COVERAGE:
            info["is_chat"] = True
            info["why"] = (
                f"指令占比 {info['coverage']:.0%} < {MIN_COVERAGE:.0%} "
                f"(剩余杂词「{info['leftover']}」太多), 按聊天处理"
            )
        else:
            info["why"] = f"指令占比 {info['coverage']:.0%} ≥ {MIN_COVERAGE:.0%}, 放行"
        return info

    def _coverage(self, clean: str, spans: list, words=None) -> dict:
        """第2+3层: 指令占比 + 句长。返回判定细节 (给测试台展示用)。"""
        if words is not None:
            return self._coverage_en(words, spans)
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
        if matched_len + len(leftover) > self.max_eff_len:
            info["is_chat"] = True
            info["why"] = f"剔除填充词后仍有 {matched_len + len(leftover)} 字 (> {self.max_eff_len}), 按聊天处理"
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

    def explain(self, text: str, boost=None) -> dict:
        """完整判定过程 (测试台/调试用)。result 字段为 None 表示不执行。

        boost: {"groups": {key: 加分}, "orders": {key: 加分}} 或 None ——
        重试助推的定向加分, 只影响指定候选。
        """
        trace = {
            "text": text, "clean": "", "chat_marker": None,
            "group": None, "order": None, "target": None, "coverage": None,
            "result": None, "reason": "",
        }
        if not text:
            trace["reason"] = "空文本"
            return trace
        clean = self._clean(text)
        trace["clean"] = clean
        if not clean:
            trace["reason"] = "只有标点/空白"
            return trace
        # 英文: 记住词边界(clean 恰是这些词无缝拼接), 占比判定按词算
        words = re.findall(r"[a-z0-9]+", text.lower()) if self.lang == "en" else None

        # 第1层: 聊天特征词
        if self.chat_filter:
            hit = next((m for m in self.chat_markers if m in clean), None)
            if hit:
                trace["chat_marker"] = hit
                trace["reason"] = f"含聊天特征词「{hit}」, 判为聊天"
                return trace

        if self.pinyin_match:
            text_py, pos2char = text_pinyin(clean)
        else:
            text_py, pos2char = "", None
        # 兵种松(叫法少,安全); 指令严(密,多同音,防乱路由)
        boost = boost or {}
        g_key, g_data, g_score, g_alias, g_span = self._best(
            clean, self.groups, text_py, pos2char, self.pinyin_group_threshold,
            boost.get("groups"))
        o_key, o_data, o_score, o_alias, o_span = self._best(
            clean, self.orders, text_py, pos2char, self.pinyin_threshold,
            boost.get("orders"))
        # 抑制"寄生"匹配: 兵种和指令抢同一段文本时, 只能活一个。
        # 指令区间比兵种多覆盖了别的字 => 指令解释了更多文本, 兵种是寄生
        #   (如"打这只军队"整句=focus_target, 兵种把"军队"蹭成"马队"→骑兵)。
        # 两者区间基本重合且兵种分更高 => 指令才是寄生
        #   (如"骑射"精确=骑射手兵种100分, 指令"开射"却谐音蹭到89分 ——
        #    光喊兵种名不该触发自由射击)。
        # 真组合(如"骑兵冲锋")两段互不包含, 不受影响。
        if (g_key and o_key and o_score >= self.order_threshold
                and _mostly_inside(g_span, o_span)):
            o_extra = (o_span[1] - o_span[0]) - max(
                0, min(o_span[1], g_span[1]) - max(o_span[0], g_span[0]))
            if o_extra >= 1:
                g_key = None      # 指令覆盖了更多字, 兵种是寄生
            elif o_score >= 100:
                g_key = None      # 同段, 指令精确/全同音 => 指令赢
            elif g_score >= 100 or o_score - g_score < 10:
                # 兵种精确(如"骑射"100 vs 谐音"开射"89), 或两边都模糊且分差
                # 拉不开(如错听"提设": 骑射80 vs 开射89, 差9) => 歧义, 宁可
                # 不发指令也不乱发 (用户重说一遍有 retry 助推接着)。
                # 分差线取10: 「炎症」圆阵93 vs 远程80差13, 是真指令要放行
                o_key = None
            else:
                g_key = None      # 同段, 指令明显更像 => 兵种让位
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
        target = None

        # 攻击类指令(takes_target)支持"骑兵进攻弓箭手"句式: 中英文里主语都在
        # 动词前、宾语在动词后。动词前的兵种=选中的自家编队, 动词后的兵种=
        # 打击目标(敌方, 显示用; 实际锁定靠准星悬停游戏原生机制)。
        # 若不区分, "骑兵进攻弓箭手"会因"弓箭手"别名更长而选中自家弓箭手 —— 反了。
        if o_data.get("takes_target") and group_ok and g_span[0] >= o_span[1]:
            # 最佳兵种出现在动词后 => 它是目标; 到动词前的文本里重找主语
            target = {"name": g_key, "alias": g_alias, "score": round(g_score),
                      "select": g_data["key"]}
            spans.append(g_span)
            prefix = clean[:o_span[0]]
            if prefix:
                if self.pinyin_match:
                    p_py, p_pos = text_pinyin(prefix)
                else:
                    p_py, p_pos = "", None
                g_key, g_data, g_score, g_alias, g_span = self._best(
                    prefix, self.groups, p_py, p_pos,
                    self.pinyin_group_threshold,
                    (boost or {}).get("groups"))
            else:
                g_key = None
            group_ok = g_key and g_score >= self.group_threshold
            trace["group"] = ({
                "name": g_key, "alias": g_alias, "score": round(g_score),
                "pass": bool(group_ok), "select": g_data["key"],
            } if g_key else None)
            trace["target"] = target
        if group_ok:
            spans.append(g_span)
        # 对称情况: 主语赢了"更长别名"的评比(如 infantry vs cavalry), 动词后的
        # 目标还没被发现 —— 再扫一次动词后的文本, 把目标补出来(显示+算入占比)。
        if (o_data.get("takes_target") and target is None and group_ok
                and g_span[1] <= o_span[0]):
            suffix = clean[o_span[1]:]
            if suffix:
                if self.pinyin_match:
                    s_py, s_pos = text_pinyin(suffix)
                else:
                    s_py, s_pos = "", None
                t_key, t_data, t_score, t_alias, t_span = self._best(
                    suffix, self.groups, s_py, s_pos, self.pinyin_group_threshold)
                if t_key and t_score >= self.group_threshold:
                    off = o_span[1]
                    target = {"name": t_key, "alias": t_alias,
                              "score": round(t_score), "select": t_data["key"]}
                    spans.append((t_span[0] + off, t_span[1] + off))
                    trace["target"] = target

        # 第2+3层: 指令占比 + 句长
        if self.chat_filter:
            cov = self._coverage(clean, spans, words)
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
        trace["result"] = {"text": text, "group": group, "order": order,
                           "target": ({"name": target["name"]} if target else None)}
        trace["reason"] = "执行"
        return trace

    def parse(self, text: str, boost=None):
        """返回 {text, group, order} 或 None (无指令/判为聊天)。"""
        return self.explain(text, boost=boost)["result"]
