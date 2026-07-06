"""语音识别封装 —— faster-whisper (本地 GPU)。"""
import os
import sys


def _add_cuda_dll_dirs():
    """让 ctranslate2 能找到 pip 装的 cuBLAS / cuDNN DLL (Windows)。"""
    try:
        import nvidia  # noqa: F401
    except ImportError:
        return
    # nvidia 是命名空间包, 用 __path__ (可能有多个根) 而非 __file__
    for base in list(getattr(nvidia, "__path__", [])):
        for sub in ("cublas", "cudnn"):
            bin_dir = os.path.join(base, sub, "bin")
            if os.path.isdir(bin_dir):
                os.add_dll_directory(bin_dir)
                os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")


_add_cuda_dll_dirs()

from faster_whisper import WhisperModel  # noqa: E402

# Whisper large-v3 在静音/噪音时常"脑补"出来的字幕话术, 命中则丢弃
HALLUCINATIONS = (
    "点赞", "订阅", "转发", "打赏", "明镜", "点点栏目",
    "字幕", "谢谢观看", "请关注", "下期再见", "MING PAO",
)


def detect_hardware():
    """探测是否有可用的 NVIDIA GPU (CUDA)。返回 (has_cuda, 说明字符串)。"""
    try:
        import ctranslate2

        n = ctranslate2.get_cuda_device_count()
        if n > 0:
            return True, f"CUDA x{n}"
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
        model = "base"
    return model, device, compute, hw


class Transcriber:
    def __init__(self, cfg: dict):
        s = cfg["stt"]
        self.language = s.get("language", "zh")
        self.beam_size = s.get("beam_size", 1)
        self.initial_prompt = s.get("initial_prompt") or None
        self.temperature = s.get("temperature", 0)
        self.vad_filter = s.get("vad_filter", True)
        model, device, compute, hw = resolve_stt_config(s)
        print(f"[STT] 硬件: {hw} -> 模型 {model} ({device}/{compute})")
        try:
            self.model = WhisperModel(model, device=device, compute_type=compute)
        except Exception as e:
            print(f"[STT] {device}/{compute} 加载失败 ({e}); 回退到 CPU/int8。",
                  file=sys.stderr)
            self.model = WhisperModel(model, device="cpu", compute_type="int8")
        print("[STT] 模型就绪。")

    def transcribe(self, audio) -> str:
        """audio: float32 单声道 numpy 数组, 16kHz。返回识别文本。"""
        segments, _ = self.model.transcribe(
            audio,
            language=self.language,
            beam_size=self.beam_size,
            initial_prompt=self.initial_prompt,
            temperature=self.temperature,   # 0 = 不做多温度重解码, 锁住延迟
            vad_filter=self.vad_filter,      # 解码前切掉静音/噪音
            condition_on_previous_text=False,
        )
        text = "".join(seg.text for seg in segments).strip()
        # 整句就是已知幻觉话术 => 当作没说话
        if text and any(h in text for h in HALLUCINATIONS):
            return ""
        return text
