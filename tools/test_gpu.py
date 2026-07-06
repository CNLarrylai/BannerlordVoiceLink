"""验证 GPU + Whisper 能正常加载并识别 (不需要麦克风)。"""
import os
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np  # noqa: E402
import yaml  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(ROOT, "config", "settings.yaml"), encoding="utf-8") as f:
    cfg = yaml.safe_load(f)

import time  # noqa: E402

from stt import Transcriber  # noqa: E402

t0 = time.time()
tr = Transcriber(cfg)
print(f"[ok] 模型加载耗时 {time.time()-t0:.1f}s")

# 1 秒静音, 只为验证识别管线不报错
silence = np.zeros(16000, dtype=np.float32)
t0 = time.time()
text = tr.transcribe(silence)
print(f"[ok] 识别管线跑通, 耗时 {time.time()-t0:.2f}s, 静音结果='{text}'")
print("GPU 测试通过 ✓")
