# -*- coding: utf-8 -*-
"""混合识别器: 流式ASR 先跑(快) + Whisper 兜底(准/抗噪)。

v2: 快路由 KWS 3M 换成流式 zipformer(~70M)+热词+matcher ——
同批真人录音: KWS 59%(且换说话人塌到72%, 阈值扫不动=声学天花板),
流式+热词 90%, 输出完整文本走 matcher(模糊/拼音/词序解析都能用)。

策略(保守混合):
  1. 流式 ASR 解码 -> matcher 解析 -> 命令 key 集合。
  2. 认出"至少一个指令(order)" => 直接用(~95ms)。
     指令是执行的最低要求(兵种可选, 只有兵种不会执行)。
  3. 否则 => 退回 Whisper + 匹配层(~180ms GPU, 抗噪, 接住快路解出
     空文本/错字太狠的)。
返回 (keys集合, 引擎名, 毫秒, 文本)。
"""
import time


class HybridRecognizer:
    """fast_text_fn(samples, sr) -> 文本; matcher 解析两路共用。"""

    def __init__(self, fast_text_fn, transcriber, matcher, commands,
                 fast_name="stream"):
        self.fast_text = fast_text_fn
        self.fast_name = fast_name
        self.tr = transcriber
        self.m = matcher
        self.orders = set(commands.get("orders", {}))

    def _keys(self, text):
        r = self.m.parse(text)
        keys = set()
        if r:
            if r.get("group"):
                keys.add(r["group"]["name"])
            if r.get("order"):
                keys.add(r["order"]["name"])
        return keys

    def recognize(self, samples, sr):
        t0 = time.perf_counter()
        ftext = self.fast_text(samples, sr)
        fkeys = self._keys(ftext)
        if fkeys & self.orders:           # 快路认出指令 => 直出
            return fkeys, self.fast_name, (time.perf_counter() - t0) * 1000, ftext
        # 慢路: Whisper 兜底
        text = self.tr.transcribe(samples)
        wkeys = self._keys(text)
        return wkeys, "whisper", (time.perf_counter() - t0) * 1000, text
