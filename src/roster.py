# -*- coding: utf-8 -*-
"""编队名册 —— 向模组问"哪个数字键是哪个兵种", 不照词典写死的 1/2/3/4。

为什么需要 (2026-09-25 查实, 起因是 YouTube 用户报 "archers 和 cavalry 反了"):
  ① 游戏里数字键 1~8 选的是**槽位号**, 槽里装什么兵是玩家在"战斗部署
     Order of Battle"界面自己定的 —— "键2=弓箭手"只是默认布局。
  ② 按了一个**没兵的槽**的键, 游戏会选中**全军**
     (MissionOrderTroopControllerVM.OnSelectFormationWithIndex 里
     找不到该槽就走 else SelectAllFormations())。队伍缺个兵种时,
     一句误听 "骑兵冲锋" 就变成全军冲锋。

所以: 有模组 → 按真实兵种成分要数字键, 缺的兵种直接拒发;
      没模组/不在战斗 → 名册未知, 维持老行为(模组随工坊一起装, 这是兜底路径)。
模组侧实现见 VoiceLinkBehavior.cs 的 ByComposition / Roster。
"""
import time

TTL = 2.0          # 缓存秒数: 战损/分队会改名册, 但不必每条指令都问一次

UNKNOWN = "unknown"    # 问不到(没模组/不在战斗) —— 不改变原有行为
MISSING = "missing"    # 问到了, 但玩家没有这支队 —— 拒发按键
OK = "ok"


class Roster:
    def __init__(self, modlink, ttl=TTL):
        self.modlink = modlink
        self.ttl = ttl
        self._map = None        # {兵种: (数字键, 人数, 成分) 或 None}; None=未知
        self._at = 0.0

    def invalidate(self):
        """进出战斗 / 分队后调用, 下次查询重新问模组。"""
        self._map = None
        self._at = 0.0

    def snapshot(self):
        """{兵种: (key,count,mix) 或 None} —— 整份名册; None = 问不到。"""
        now = time.monotonic()
        if self._map is not None and now - self._at < self.ttl:
            return self._map
        self._at = now
        self._map = self._fetch()
        return self._map

    def _fetch(self):
        if not self.modlink:
            return None
        r = self.modlink.roster()
        if not r or not r.startswith("ok"):
            return None            # err no_battle / 模组不在 => 未知
        out = {}
        for tok in r.split()[1:]:
            name, sep, val = tok.partition("=")
            if not sep or not name:
                return None        # 协议对不上, 宁可当未知也不瞎发键
            if val == "-":
                out[name] = None   # 明确"没有这支队"
                continue
            f = val.split(":")
            try:
                out[name] = (f[0], int(f[1]), f[2] if len(f) > 2 else "")
            except (ValueError, IndexError):
                return None
        return out or None

    def resolve(self, group):
        """查某兵种。返回 (状态, 数字键, 人数, 成分):
          OK      -> 按这个数字键(可能和词典里写的不一样)
          MISSING -> 玩家没有这支队, 一个键都别发
          UNKNOWN -> 问不到, 照词典原样发
        """
        m = self.snapshot()
        if m is None or group not in m:
            return (UNKNOWN, None, 0, "")
        info = m[group]
        if info is None:
            return (MISSING, None, 0, "")
        return (OK, info[0], info[1], info[2])

    def line(self):
        """一行人类可读的名册, 给日志/排错用。"""
        m = self.snapshot()
        if m is None:
            return "名册未知(模组不在或不在战斗)"
        bits = []
        for name, info in m.items():
            bits.append(f"{name}=无" if info is None
                        else f"{name}=键{info[0]}({info[1]}人 {info[2]})")
        return " ".join(bits)
