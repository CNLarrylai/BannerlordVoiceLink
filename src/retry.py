"""重试助推 + 回声抑制 —— 利用"连续几句话之间有关联"这个原本被丢掉的信号。

洞察(用户提出): 指令没识别对时, 人会本能地马上再说一遍。反过来, 刚执行过
的指令又立刻出现, 多半是回音/黏连而不是新命令。两件事是同一枚硬币的两面,
必须一起设计, 否则"放大重试"会把回声也放大成连发:

  - 上一句有"差点命中"的候选且没执行对 -> 这一句又很相似 => 判为重说,
    只给那几条候选定向加分(不放松其它任何指令), 并把它们的说法作为
    hotwords 喂给识别器, 提高这一遍听准的概率。
  - 刚执行过 -> 冷却期内又解析出同一条(同兵种+同指令) => 判为回声, 忽略。

宁窄勿宽: 放大只作用于明确的重试场景 + 明确的候选, 整体阈值一分不降。
"""
import time

from rapidfuzz import fuzz


class RetryMemory:
    # 重说判定的相似度门槛: 实测真重试(含再次听岔) 75~100 分, 无关闲聊 0~46 分,
    # 取 60 两边各留 ~15 分余量。
    MIN_SIMILARITY = 60

    def __init__(self, window_sec=8.0, cooldown_sec=2.5, bonus=12,
                 min_similarity=None, enabled=True):
        self.window = float(window_sec)
        self.cooldown = float(cooldown_sec)
        self.bonus = int(bonus)
        self.min_similarity = (self.MIN_SIMILARITY if min_similarity is None
                               else min_similarity)
        self.enabled = enabled
        self._miss = None    # {"t", "text", "groups": {key: 别名}, "orders": {...}}
        self._exec = None    # {"t", "group", "order"}

    # ---------- 记录 ----------

    def note_miss(self, text, groups, orders, now=None):
        """记下"差点命中": groups/orders = {key: 命中的别名} (可为空 dict)。"""
        if not self.enabled or not (groups or orders):
            return
        self._miss = {"t": time.monotonic() if now is None else now,
                      "text": (text or "").lower(),
                      "groups": dict(groups or {}),
                      "orders": dict(orders or {})}

    def note_exec(self, group_key, order_key, now=None):
        """记下刚执行的指令 (回声判定基准); 同时清掉重试状态 (目的已达成)。"""
        if not self.enabled:
            return
        self._exec = {"t": time.monotonic() if now is None else now,
                      "group": group_key, "order": order_key}
        self._miss = None

    # ---------- 查询 ----------

    def _miss_fresh(self, now):
        return self._miss is not None and (now - self._miss["t"]) <= self.window

    def boost_for(self, text, now=None):
        """这一句是不是"重说"? 是则返回 (定向加分表, 说明), 否则 (None, "")。"""
        now = time.monotonic() if now is None else now
        if not self.enabled or not text or not self._miss_fresh(now):
            return None, ""
        sim = fuzz.partial_ratio(self._miss["text"], text.lower())
        if sim < self.min_similarity:
            return None, ""
        boost = {"groups": {k: self.bonus for k in self._miss["groups"]},
                 "orders": {k: self.bonus for k in self._miss["orders"]}}
        names = list(self._miss["groups"]) + list(self._miss["orders"])
        why = (f"疑似重说 (与上句相似 {sim:.0f}%), 定向放大候选: "
               f"{', '.join(names)} (+{self.bonus}分)")
        return boost, why

    def hotwords(self, now=None):
        """重试窗口内, 返回差点命中的说法串 (喂给 Whisper hotwords 偏置听音)。"""
        now = time.monotonic() if now is None else now
        if not self.enabled or not self._miss_fresh(now):
            return None
        seen, out = set(), []
        for al in (list(self._miss["groups"].values())
                   + list(self._miss["orders"].values())):
            if al and al not in seen:
                seen.add(al)
                out.append(al)
        return ", ".join(out) if out else None

    def is_echo(self, group_key, order_key, now=None):
        """冷却期内又解析出同一条 (同兵种+同指令) => 判为回声/黏连。"""
        now = time.monotonic() if now is None else now
        if not self.enabled or self._exec is None:
            return False
        return ((now - self._exec["t"]) <= self.cooldown
                and self._exec["group"] == group_key
                and self._exec["order"] == order_key)
