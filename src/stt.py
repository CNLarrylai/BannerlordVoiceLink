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


def _cuda_libs_available():
    """CUDA 运行库(cuBLAS/cuDNN)在不在。

    源码: 装了 nvidia-*-cu12 就有。打包 CPU 版故意不带 -> 导入失败 -> False,
    这样即便机器有 GPU 也会退回 CPU, 不会 cublas64_12.dll not found。
    """
    try:
        import nvidia.cublas  # noqa: F401
        import nvidia.cudnn   # noqa: F401
        return True
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
        model = "base"
    return model, device, compute, hw


def bundled_model_path(model: str) -> str:
    """解析模型引用。

    源码: 直接返回模型名, faster-whisper 自己找缓存/联网下载。
    打包: 优先内置目录; 其次本机已下载的缓存; 都没有则退回内置 base ——
          这样粉丝(CPU包)误选了 large-v3 又下不动时不会崩, 自动用 base。
    """
    base = getattr(sys, "_MEIPASS", None)
    if not base:
        return model
    p = os.path.join(base, "models", f"faster-whisper-{model}")
    if os.path.isdir(p):
        return p
    cache = os.path.expanduser(
        f"~/.cache/huggingface/hub/models--Systran--faster-whisper-{model}")
    if os.path.isdir(cache):
        return model  # 用户下过, faster-whisper 会用缓存
    fb = os.path.join(base, "models", "faster-whisper-base")
    if os.path.isdir(fb):
        print(f"[STT] 模型 {model} 未内置且未下载, 退回内置 base。")
        return fb
    return model


class Transcriber:
    def __init__(self, cfg: dict):
        s = cfg["stt"]
        self.language = s.get("language", "zh")
        self.beam_size = s.get("beam_size", 1)
        if self.language == "en":
            # 英文用英文提示词偏置 (中文提示词会干扰英文识别)
            self.initial_prompt = s.get("initial_prompt_en") or (
                "Commanding an army in battle. Troops: infantry, archers, "
                "cavalry, horse archers. Orders: charge, advance, retreat, halt, "
                "follow me, shield wall, form a line, fire at will, hold fire.")
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
