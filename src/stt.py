"""语音识别封装 —— faster-whisper (本地 GPU)。"""
import os
import re
import sys


def _add_cuda_dll_dirs():
    """把所有可能的 CUDA DLL 目录加进搜索路径 (pip包 / 下载的 / 系统)。"""
    try:
        import cuda_libs
        cuda_libs.add_to_search_path()
    except Exception:
        pass


_add_cuda_dll_dirs()

from faster_whisper import WhisperModel  # noqa: E402

# Whisper large-v3 在静音/噪音时常"脑补"出来的字幕话术, 命中则丢弃
HALLUCINATIONS = (
    "点赞", "订阅", "转发", "打赏", "明镜", "点点栏目",
    "字幕", "谢谢观看", "请关注", "下期再见", "MING PAO",
)

# 退化循环检测: temperature=0 关掉了质量回退(为锁延迟), Whisper 偶发的
# 重复环("轻轻轻轻轻…")会漏出来 —— 用文本形态兜底, 零解码开销。
_CHAR_LOOP_RE = re.compile(r"(.)\1{5,}")            # 同一字符连续 6+
_WORD_LOOP_RE = re.compile(r"(.{2,8}?)\1{2,}")      # 同一 2~8 字片段连续 3+


def looks_degenerate(text: str) -> bool:
    """是不是重复幻觉/退化输出 (真人指令不会长这样)。"""
    if not text:
        return False
    core = re.sub(r"[\s,。、!！?？.…~]+", "", text)
    if _CHAR_LOOP_RE.search(core) or _WORD_LOOP_RE.search(core):
        return True
    # 压缩比思想: 够长但字符种类极少 ("轻轻 轻轻 轻轻…")
    if len(core) >= 8 and len(set(core)) <= max(2, len(core) // 6):
        return True
    return False


def _cuda_libs_available():
    """CUDA 运行库(cuBLAS/cuDNN)这台机器上找得到吗。

    位置感知: pip 装的(源码/GPU包) / 下载到 %LOCALAPPDATA% 的 / 系统 CUDA,
    任一来源有就算有。CPU 通用包默认三处都没有 -> False -> 退回 CPU;
    用户在音频设置里点下载后 -> 下载目录里有 -> True -> 自动走 GPU。
    """
    try:
        import cuda_libs
        return cuda_libs.is_ready()
    except Exception:
        return False


def detect_hardware():
    """探测能否真正用 GPU (既要有设备, 也要有 CUDA 运行库)。"""
    try:
        import ctranslate2

        n = ctranslate2.get_cuda_device_count()
        if n > 0 and _cuda_libs_available():
            return True, f"CUDA x{n}"
        if n > 0:
            return False, "CPU (检测到GPU但无CUDA运行库, 用CPU)"
    except Exception:
        pass
    return False, "CPU (无可用 CUDA)"


def resolve_stt_config(s: dict):
    """把 auto 解析成具体的 (model, device, compute)。

    model=auto  -> base (实测甜蜜点: 命中率≈small, 速度≈快一倍, CPU 上也能用)
    device=auto -> 有 N 卡 cuda, 否则 cpu
    compute=auto-> cuda 用 float16, cpu 用 int8
    显式写的值优先, 保持向后兼容。
    """
    has_cuda, hw = detect_hardware()
    device = s.get("device") or "auto"
    if device == "auto":
        device = "cuda" if has_cuda else "cpu"
    compute = s.get("compute_type") or "auto"
    if compute == "auto":
        compute = "float16" if device == "cuda" else "int8"
    model = s.get("model") or "auto"
    if model == "auto":
        # 按实际算力分档(2026-08 实测, 纯CPU/int8, TTS语料24条):
        #   base 0.56s 92% | small 1.70s 100% | medium 5.0s | turbo 6.2s
        # 有 CUDA(且运行库齐) -> turbo: GPU上~0.2s, 最准的兜底。
        # 无 CUDA -> small 若已下载就用它(命中拉满, 1.7s 可接受, 兜底才走,
        #   日常是快路0.1s); 没下过就用内置 base —— 0.9.11 起包里只带 base,
        #   不能让 auto 指向一个要联网下 464MB 的模型(否则新用户首启就卡在下载)。
        #   turbo 在 CPU 上 6 秒, 粉丝会以为卡死 —— 绝不能当默认。
        if device == "cuda":
            model = "large-v3-turbo"
        else:
            model = "small" if model_available("small") else "base"
    return model, device, compute, hw


def _own_dir(model: str):
    """这个模型**自己**的本地目录(手动放的 / 内置进包的), 没有就 None。

    必须和 bundled_model_path 分开: 后者带"找不到就退回内置 base"的兜底,
    拿它判断"有没有 small"会永远为真(实测: small 缺失时它返回 base 的目录)。
    """
    try:
        from paths import user_data_dir
        manual = os.path.join(user_data_dir(), "models", model)
        if os.path.isfile(os.path.join(manual, "model.bin")):
            return manual
    except Exception:
        pass
    base = getattr(sys, "_MEIPASS", None)
    if base:
        p = os.path.join(base, "models", f"faster-whisper-{model}")
        if os.path.isdir(p):
            return p
    return None


def model_available(model: str) -> bool:
    """这个模型现在就能用吗(不用联网)? 内置进包 / 手动放的目录 / 已下载的缓存
    三者任一都算。

    别直接用 models.is_ready() 判断"要不要下载" —— 它只看缓存和手动目录,
    看不见**内置进包**的模型, 于是打包版会把已经内置的 base 再下一遍
    (新用户白下 145MB, listen.py 首启踩过)。
    """
    if _own_dir(model):
        return True
    try:
        import models
        return bool(models.is_ready(model))
    except Exception:
        return False


def bundled_model_path(model: str) -> str:
    """解析模型引用。

    源码: 直接返回模型名, faster-whisper 自己找缓存/联网下载。
    打包: 优先内置目录; 其次本机已下载的缓存; 都没有则退回内置的
          small -> base —— 粉丝选了 large-v3 又下不动时不会崩。
    """
    # 手动放模型的简易目录(所有形态都先看这里): 教粉丝建
    # %LOCALAPPDATA%\BannerlordVoice\models\<模型名>\ 比让他们手搓
    # ~/.cache/huggingface/hub/models--Systran--faster-whisper-x/snapshots/y
    # 那串路径靠谱得多 —— 目录名错一个字就前功尽弃(实测常见求助点)。
    own = _own_dir(model)       # 手动放的目录 / 内置进包的目录
    if own:
        return own
    base = getattr(sys, "_MEIPASS", None)
    if not base:
        return model            # 源码形态: 交给 faster-whisper 自己找/下
    # 已下载到 HF 缓存的 => 交给 faster-whisper 按名字解析。仓库名必须走
    # models.model_repo 的映射, 不能写死 Systran: large-v3-turbo 在
    # mobiuslabsgmbh 下, 曾因此"永远找不到"而静默回退 small —— 打包版里
    # 用户选 turbo / GPU 引导装完 turbo 都白选(2026-09-02 用户实测发现)。
    try:
        import models
        if models.is_ready(model):
            return model
    except Exception:
        pass
    for fb_name in ("small", "base"):   # 兜底顺序: 好的优先
        fb = os.path.join(base, "models", f"faster-whisper-{fb_name}")
        if os.path.isdir(fb):
            print(f"[STT] 模型 {model} 未内置且未下载, 退回内置 {fb_name}。")
            return fb
    return model


class Transcriber:
    def __init__(self, cfg: dict):
        s = cfg["stt"]
        self.language = s.get("language", "zh")
        self.beam_size = s.get("beam_size", 1)
        if self.language == "en":
            # 英文用英文提示词偏置 (中文提示词会干扰英文识别)
            # 写成"前文转写"的样子(短句+叹号)比罗列词表偏置更强: Whisper 把
            # prompt 当上一段字幕, 会模仿其句式/用词。重点铺 "All units, ..."
            # —— 非母语口音下 All 常被听成 Or/Oh, 靠这里把它拉回来。
            self.initial_prompt = s.get("initial_prompt_en") or (
                "All units, charge! All units, follow me! All units, hold "
                "position! Infantry, shield wall! Infantry, advance! Archers, "
                "fire at will! Archers, hold fire! Cavalry, charge! Cavalry, "
                "flank them! Horse archers, fall back! Everyone, retreat! "
                "Infantry, form a line! Cavalry, split! Archers, spread out!")
        else:
            self.initial_prompt = s.get("initial_prompt") or None
        self.temperature = s.get("temperature", 0)
        self.vad_filter = s.get("vad_filter", True)
        model, device, compute, hw = resolve_stt_config(s)
        model = bundled_model_path(model)
        print(f"[STT] 硬件: {hw} -> 模型 {model} ({device}/{compute})")
        try:
            self.model = WhisperModel(model, device=device, compute_type=compute)
        except Exception as e:
            print(f"[STT] {device}/{compute} 加载失败 ({e}); 回退到 CPU/int8。",
                  file=sys.stderr)
            self.model = WhisperModel(model, device="cpu", compute_type="int8")
        # hotwords: 重试助推时把差点命中的说法喂给解码器偏置 (旧版 faster-whisper 没有)
        try:
            import inspect
            self._hotwords_ok = "hotwords" in inspect.signature(
                self.model.transcribe).parameters
        except Exception:
            self._hotwords_ok = False
        print(f"[STT] 模型就绪。{'(支持热词偏置)' if self._hotwords_ok else ''}")

    def transcribe(self, audio, hotwords=None) -> str:
        """audio: float32 单声道 numpy 数组, 16kHz。返回识别文本。

        hotwords: 可选说法串, 偏置解码器往这些词上听 (重试助推用)。
        """
        kw = {}
        if hotwords and self._hotwords_ok:
            kw["hotwords"] = hotwords
        segments, _ = self.model.transcribe(
            audio,
            language=self.language,
            beam_size=self.beam_size,
            initial_prompt=self.initial_prompt,
            temperature=self.temperature,   # 0 = 不做多温度重解码, 锁住延迟
            vad_filter=self.vad_filter,      # 解码前切掉静音/噪音
            condition_on_previous_text=False,
            **kw,
        )
        text = "".join(seg.text for seg in segments).strip()
        # 整句就是已知幻觉话术 => 当作没说话
        if text and any(h in text for h in HALLUCINATIONS):
            return ""
        # 重复退化("轻轻轻轻…") => 丢弃并留痕, 别让它去撞词典
        if looks_degenerate(text):
            print(f"[STT] ⚠ 检出重复幻觉, 已丢弃: 「{text[:30]}…」")
            return ""
        return text
