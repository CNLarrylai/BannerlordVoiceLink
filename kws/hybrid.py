# -*- coding: utf-8 -*-
"""混合识别器: KWS 先跑(快) + Whisper 兜底(准/抗口音)。

策略(保守混合):
  1. KWS 流式识别 -> 命中的命令 key 集合。
  2. KWS 认出"至少一个指令(order)" => 直接用 KWS 结果(~24ms 秒响应)。
     指令是执行的最低要求(兵种可选, 只有兵种不会执行)。
  3. 否则(空/只有兵种) => 退回 Whisper + 匹配层(~260ms, 抗口音, 接住 KWS
     换说话人漏掉的 —— 真人数据: KWS 你85%/你老婆72%, Whisper 88%/93%)。
返回 (keys集合, 引擎名, 毫秒, whisper文本)。
"""
import time


class HybridRecognizer:
    def __init__(self, kws, kws_spot, transcriber, matcher, commands):
        self.kws = kws
        self.kws_spot = kws_spot          # (kws, samples, sr) -> {command_key}
        self.tr = transcriber
        self.m = matcher
        self.orders = set(commands.get("orders", {}))

    def recognize(self, samples, sr):
        t0 = time.perf_counter()
        kkeys = self.kws_spot(self.kws, samples, sr)
        if kkeys & self.orders:           # KWS 认出指令 => 快路
            return kkeys, "kws", (time.perf_counter() - t0) * 1000, ""
        # 慢路: Whisper 兜底
        text = self.tr.transcribe(samples)
        r = self.m.parse(text)
        wkeys = set()
        if r:
            if r.get("group"):
                wkeys.add(r["group"]["name"])
            if r.get("order"):
                wkeys.add(r["order"]["name"])
        return wkeys, "whisper", (time.perf_counter() - t0) * 1000, text
