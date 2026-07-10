# -*- coding: utf-8 -*-
"""流式 zipformer ASR (sherpa-onnx, 双语 zh-en ~70M参数) —— 混合识别的快路。

定位: CPU 上 ~90ms 出完整文本, 走现有 matcher(模糊/拼音/词序/个人词典全生效),
解不出指令时由 Whisper 兜底(见 main._transcribe)。真人两轮实测(2026-07):
她 90% / 老婆 97%, 均≥Whisper, 延迟约一半; 换说话人不塌(KWS 3M 就死在这)。

关键工程点:
- 热词必开: 裸模型79% -> 加热词90%。按建模单元写(中文单字空格分开,
  字必须在 tokens.txt 里), 每命令取前2个主别名, 全塞会稀释偏置。
- 峰值归一化到0.5必做: 模型对输入电平敏感, 麦克风偏小声(rms~0.03)整句
  吐空文本; 0.9太猛会把"随我来"推成"所有来"。只拉小声的, 大声的不动。
"""
import os

import numpy as np

from paths import FROZEN, bundle_dir, log_dir

# 打包时模型放包内 models/ (只带 int8 encoder, 见 app.spec); 源码用 kws/ 下载版
_SRC_MODEL = os.path.join(
    bundle_dir(), "kws", "models",
    "sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20")
_PKG_MODEL = os.path.join(bundle_dir(), "models", "streaming-zipformer-zh-en")

_FILES = ("encoder-epoch-99-avg-1.int8.onnx", "decoder-epoch-99-avg-1.onnx",
          "joiner-epoch-99-avg-1.int8.onnx", "tokens.txt")


def model_dir():
    return _PKG_MODEL if FROZEN else _SRC_MODEL


def available():
    """(能否用, 原因)。缺库/缺模型都优雅退回纯 Whisper, 不挡启动。"""
    try:
        import sherpa_onnx  # noqa: F401
    except Exception as e:
        return False, f"sherpa-onnx 库不可用: {e}"
    d = model_dir()
    missing = [f for f in _FILES if not os.path.exists(os.path.join(d, f))]
    if missing:
        return False, f"模型文件缺失: {missing[0]} (目录 {d})"
    return True, ""


def build_hotwords(commands, path=None, per_cmd=2):
    """由命令词典(含个人词典)生成热词文件, 返回路径。

    sherpa-onnx 要求按建模单元写: 中文=单字空格分开, 且字必须在 tokens.txt
    里(不在词表的别名跳过, 否则加载直接报错)。
    """
    path = path or os.path.join(log_dir(), "hotwords_zh.txt")
    vocab = set()
    with open(os.path.join(model_dir(), "tokens.txt"), encoding="utf-8") as f:
        for line in f:
            vocab.add(line.split()[0])
    with open(path, "w", encoding="utf-8") as f:
        for sec in ("groups", "orders"):
            for d in commands.get(sec, {}).values():
                for a in (d.get("aliases") or [])[:per_cmd]:
                    chars = list(a)
                    if all(c in vocab for c in chars):
                        f.write(" ".join(chars) + "\n")
    return path


def make_stream(hotwords_file=None, hotwords_score=1.5):
    import sherpa_onnx
    d = model_dir()
    kw = {}
    if hotwords_file:
        kw = dict(hotwords_file=hotwords_file, hotwords_score=hotwords_score,
                  decoding_method="modified_beam_search")
    return sherpa_onnx.OnlineRecognizer.from_transducer(
        tokens=os.path.join(d, "tokens.txt"),
        encoder=os.path.join(d, "encoder-epoch-99-avg-1.int8.onnx"),
        decoder=os.path.join(d, "decoder-epoch-99-avg-1.onnx"),
        joiner=os.path.join(d, "joiner-epoch-99-avg-1.int8.onnx"),
        num_threads=2, sample_rate=16000, feature_dim=80, **kw)


def transcribe(rec, samples, sr):
    """整段解码 -> 文本 (峰值归一 + 末尾垫0.5s静音把尾字冲出来)。"""
    peak = float(abs(samples).max()) if len(samples) else 0.0
    if 1e-4 < peak < 0.5:
        samples = samples * (0.5 / peak)
    st = rec.create_stream()
    st.accept_waveform(sr, samples)
    st.accept_waveform(sr, np.zeros(int(sr * 0.5), dtype="float32"))
    st.input_finished()
    while rec.is_ready(st):
        rec.decode_stream(st)
    return rec.get_result(st)


class FastTranscriber:
    """给 main 用的封装: 建引擎+热词, 支持词典热重载后重建。"""

    def __init__(self, commands):
        self.rec = make_stream(build_hotwords(commands))

    def transcribe(self, audio, sr=16000):
        return transcribe(self.rec, audio, sr)

    def rebuild(self, commands):
        """词典变了(F10 热重载/校准学了新词) -> 热词跟着刷新。"""
        self.rec = make_stream(build_hotwords(commands))
