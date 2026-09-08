# -*- coding: utf-8 -*-
"""模型下载源回退 (正确性门槛)。

教训(2026-09-09 新用户模拟): HF_ENDPOINT 曾全局写死 hf-mirror.com, 该站变成 308 跳转后
所有下载必失败。现在 download() 按 endpoints() 逐个试, 全失败给用户一句能行动的话。
不联网: _snapshot / _repo_total_bytes 被替换。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import models  # noqa: E402


def _patch(fail_on):
    calls = []

    def fake_snapshot(repo, endpoint):
        calls.append(endpoint)
        if endpoint in fail_on:
            raise ConnectionError("boom " + endpoint)

    models._snapshot = fake_snapshot
    models._repo_total_bytes = lambda repo, endpoint=None: 0
    models._downloaded_bytes = lambda model: 0
    return calls


def test_endpoints_order_and_dedupe():
    os.environ.pop("HF_ENDPOINT", None)
    eps = models.endpoints()
    assert eps[0] == "https://huggingface.co", eps
    assert "https://hf-mirror.com" in eps and len(eps) == len(set(eps))
    os.environ["HF_ENDPOINT"] = "https://my-proxy.example/"
    eps = models.endpoints()
    assert eps[0] == "https://my-proxy.example", eps      # 用户自设优先, 去尾斜杠
    os.environ["HF_ENDPOINT"] = "https://huggingface.co"
    assert models.endpoints().count("https://huggingface.co") == 1
    os.environ.pop("HF_ENDPOINT", None)


def test_falls_back_to_next_source():
    os.environ.pop("HF_ENDPOINT", None)
    calls = _patch(fail_on={"https://huggingface.co"})
    assert models.download("small") is True
    assert calls == ["https://huggingface.co", "https://hf-mirror.com"], calls


def test_first_source_success_stops():
    os.environ.pop("HF_ENDPOINT", None)
    calls = _patch(fail_on=set())
    assert models.download("small") is True
    assert calls == ["https://huggingface.co"], calls


def test_all_fail_gives_actionable_message():
    os.environ.pop("HF_ENDPOINT", None)
    _patch(fail_on={"https://huggingface.co", "https://hf-mirror.com"})
    try:
        models.download("large-v3-turbo")
        assert False, "应抛 ModelDownloadError"
    except models.ModelDownloadError as e:
        s = str(e)
        assert "huggingface.co" in s and "hf-mirror.com" in s, s
        assert "models\\large-v3-turbo" in s and "model.bin" in s, s


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
