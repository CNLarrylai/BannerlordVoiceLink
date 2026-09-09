# -*- coding: utf-8 -*-
"""模型下载源回退 (正确性门槛)。

教训(2026-09-09 新用户模拟): HF_ENDPOINT 曾全局写死 hf-mirror.com, 该站变成 308 跳转后
所有下载必失败。现在 download() 按 endpoints() 逐个试(先 4s 探通), HF 系全败再走
ModelScope(国内可达, 落到手动目录), 全失败给用户一句能行动的话。不联网: 网络函数全替换。
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import models  # noqa: E402

HF = "https://huggingface.co"
MIRROR = "https://hf-mirror.com"
MS = models.MODELSCOPE


def _patch(fail_on, unreachable=(), ms_ok=True):
    calls = []

    def fake_snapshot(repo, endpoint):
        calls.append(endpoint)
        if endpoint in fail_on:
            raise ConnectionError("boom " + endpoint)

    def fake_ms(model, repo, progress_cb=None):
        calls.append(MS)
        if not ms_ok:
            raise ConnectionError("boom modelscope")
        if progress_cb:
            progress_cb(5, 10)
            progress_cb(10, 10)
        return True

    models._snapshot = fake_snapshot
    models._modelscope_download = fake_ms
    models._reachable = lambda url, timeout=4: not any(url.startswith(u) for u in unreachable)
    models._repo_total_bytes = lambda repo, endpoint=None: 0
    models._downloaded_bytes = lambda model: 0
    os.environ.pop("HF_ENDPOINT", None)
    return calls


def test_endpoints_order_and_dedupe():
    os.environ.pop("HF_ENDPOINT", None)
    eps = models.endpoints()
    assert eps[0] == HF, eps
    assert MIRROR in eps and len(eps) == len(set(eps))
    os.environ["HF_ENDPOINT"] = "https://my-proxy.example/"
    eps = models.endpoints()
    assert eps[0] == "https://my-proxy.example", eps      # 用户自设优先, 去尾斜杠
    os.environ["HF_ENDPOINT"] = HF
    assert models.endpoints().count(HF) == 1
    os.environ.pop("HF_ENDPOINT", None)


def test_first_source_success_stops():
    calls = _patch(fail_on=set())
    assert models.download("small") is True
    assert calls == [HF], calls


def test_falls_back_hf_to_mirror_to_modelscope():
    calls = _patch(fail_on={HF, MIRROR})
    prog = []
    assert models.download("small", lambda d, t: prog.append((d, t))) is True
    assert calls == [HF, MIRROR, MS], calls
    assert prog[-1] == (10, 10), prog          # 魔搭路径也报进度


def test_unreachable_sources_are_skipped_fast():
    # 国内典型: hf.co / 镜像 4 秒无回应 -> 不等 hub 库超时, 直接魔搭
    calls = _patch(fail_on=set(), unreachable=(HF, MIRROR))
    assert models.download("small") is True
    assert calls == [MS], calls


def test_all_fail_gives_actionable_message():
    _patch(fail_on={HF, MIRROR}, unreachable=(), ms_ok=False)
    try:
        models.download("large-v3-turbo")
        assert False, "应抛 ModelDownloadError"
    except models.ModelDownloadError as e:
        s = str(e)
        assert "huggingface.co" in s and "hf-mirror.com" in s and "modelscope.cn" in s, s
        assert "models\\large-v3-turbo" in s and "model.bin" in s, s


def test_manual_dir_counts_as_ready():
    tmp = tempfile.mkdtemp()
    models.manual_dir = lambda model: os.path.join(tmp, model)
    assert not models.is_ready("medium")
    os.makedirs(os.path.join(tmp, "medium"))
    with open(os.path.join(tmp, "medium", "model.bin"), "wb") as f:
        f.write(b"\0" * 21_000_000)
    assert models.is_ready("medium")


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8")
        except Exception:
            pass
    fails = 0
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  ✓ {name}")
            except AssertionError as e:
                fails += 1
                print(f"  ✗✗✗ {name}: {e}")
    print(f"\n{'❌ 有失败' if fails else '✓ 模型下载源回退全部通过'}")
    sys.exit(1 if fails else 0)
