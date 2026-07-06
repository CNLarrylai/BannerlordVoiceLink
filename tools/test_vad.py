"""离线测 VAD 断句状态机 (合成音频, 不用麦克风)。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np  # noqa: E402

from audio import ContinuousListener  # noqa: E402

SR = 16000
cfg = {
    "audio": {"samplerate": SR, "device": None},
    "vad": {
        "start_rms": 0.02, "end_rms": 0.012, "end_silence_sec": 0.6,
        "min_speech_sec": 0.3, "max_speech_sec": 8.0, "preroll_sec": 0.25,
    },
}
L = ContinuousListener(cfg)
FRAME = L.frame_len
frame_sec = L.frame_ms / 1000.0


def frames_of(seconds, amp):
    """生成 seconds 秒、给定振幅的若干帧 (白噪声模拟说话/静音)。"""
    n = int(round(seconds / frame_sec))
    out = []
    for _ in range(n):
        if amp > 0:
            out.append((np.random.randn(FRAME) * amp).astype(np.float32))
        else:
            out.append(np.zeros(FRAME, dtype=np.float32))
    return out


def run(label, frames, expect_segments):
    L._reset()
    segs = [s for f in frames if (s := L.feed(f)) is not None]
    durs = [round(len(s) / SR, 2) for s in segs]
    ok = "✓" if len(segs) == expect_segments else "✗"
    print(f"  {ok} {label}: 切出 {len(segs)} 段 (期望 {expect_segments}) 时长={durs}")


np.random.seed(0)
LOUD, QUIET = 0.08, 0.0  # 说话 / 静音

print("=== VAD 断句测试 ===")
# 1) 静音 -> 不应切出任何段
run("纯静音 2s", frames_of(2.0, QUIET), 0)
# 2) 一句话: 静音0.5 + 说话1.5 + 静音1.0 -> 1 段
run("单句", frames_of(0.5, QUIET) + frames_of(1.5, LOUD) + frames_of(1.0, QUIET), 1)
# 3) 两句话: 中间隔 1s 静音 -> 2 段
run(
    "两句(隔1s)",
    frames_of(0.3, QUIET) + frames_of(1.0, LOUD) + frames_of(1.0, QUIET)
    + frames_of(1.0, LOUD) + frames_of(0.8, QUIET),
    2,
)
# 4) 太短的一句 (0.15s) -> 被 min_speech 过滤, 0 段
run("极短杂音", frames_of(0.5, QUIET) + frames_of(0.15, LOUD) + frames_of(0.8, QUIET), 0)
print("完成。")
