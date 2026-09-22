# -*- coding: utf-8 -*-
"""模型下载: 多源测速择优 / 断点续传换源 / sha256 校验 (正确性门槛)。

不联网: 每个"下载源"是本机起的真 HTTP 服务, 按场景模拟网络状况。
"国内场景"的设定来自 2026-09-22 Globalping 大陆探针实测:
  hf.co = TCP 连不上(黑洞); hf-mirror = 元数据秒回, model.bin 跳到美国 xet CDN,
  下一点就卡住; 魔搭 = 正常。旧实现在这个场景下永远卡在 hf-mirror —— 本文件锁住它。
"""
import hashlib
import http.server
import json
import os
import random
import socket
import socketserver
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import models  # noqa: E402

random.seed(7)
BIN = bytes(random.getrandbits(8) for _ in range(3_000_000))
CFG = b'{"alignment_heads": []}'
FILES = {"model.bin": BIN, "config.json": CFG, "README.md": b"readme"}
SHA = {k: hashlib.sha256(v).hexdigest() for k, v in FILES.items()}
REPO = models.model_repo("small")

# 小超时让场景几秒内跑完
models.PROBE_SECS = 0.6
models.PROBE_BYTES = 1 << 20
models.LIST_TIMEOUT = 1.5
models.READ_TIMEOUT = 1.0
models.SLOW_WINDOW = 0.6
models.SLOW_BPS = 200 << 10
models._CACHE = tempfile.mkdtemp()   # 别读到本机真实 HF 缓存


class _Srv(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def serve(kind, mode="ok", stall_after=None):
    """起一个假下载源。mode: ok / slow(20KB/s) / medium(~2MB/s) / stall_full(整文件下载到 stall_after 字节卡住,
    测速和续传请求正常) / stall_all(所有 model.bin 请求到 stall_after 卡住) / corrupt。
    返回 (base_url, 请求记录)。"""
    log = []

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            p = self.path.split("?")[0]
            log.append((p, self.headers.get("Range")))
            if kind == "hf" and p == f"/api/models/{REPO}/tree/main":
                body = json.dumps([{"type": "file", "path": n, "size": len(v),
                                    **({"lfs": {"oid": SHA[n]}} if n == "model.bin" else {})}
                                   for n, v in FILES.items()]).encode()
                return self._send(200, body)
            if kind == "ms" and p == f"/api/v1/models/{REPO}/repo/files":
                body = json.dumps({"Data": {"Files": [
                    {"Path": n, "Size": len(v), "Sha256": SHA[n], "Type": "blob"}
                    for n, v in FILES.items()]}}).encode()
                return self._send(200, body)
            name = p.rsplit("/", 1)[-1]
            if "/resolve/" not in p or name not in FILES:
                return self._send(404, b"nope")
            data = FILES[name]
            if mode == "corrupt" and name == "model.bin":
                data = b"\x00" + data[1:]
            rng = self.headers.get("Range")
            start, end = 0, len(data) - 1
            if rng:
                a, b = rng.split("=")[1].split("-")
                start, end = int(a), (int(b) if b else len(data) - 1)
            chunk = data[start:end + 1]
            self.send_response(206 if rng else 200)
            self.send_header("Content-Length", str(len(chunk)))
            if rng:
                self.send_header("Content-Range", f"bytes {start}-{end}/{len(data)}")
            self.end_headers()
            stall = name == "model.bin" and (mode == "stall_all" or
                                             (mode == "stall_full" and not rng))
            step = 4096 if mode == "slow" else 65536
            sent = 0
            try:
                for i in range(0, len(chunk), step):
                    if stall and sent >= stall_after:
                        time.sleep(30)
                        return
                    self.wfile.write(chunk[i:i + step])
                    sent += step
                    if mode == "slow":
                        time.sleep(0.2)
                    elif mode == "medium":
                        time.sleep(0.03)
            except (ConnectionError, OSError):
                pass

        def _send(self, code, body):
            self.send_response(code)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    s = _Srv(("127.0.0.1", 0), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{s.server_address[1]}", log


def blackhole():
    """接受 TCP 但从不回应 —— 大陆连 hf.co 的样子。"""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen(50)
    return f"http://127.0.0.1:{sock.getsockname()[1]}", sock


def dead():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()                         # 端口关着 = 连接被拒
    return f"http://127.0.0.1:{port}"


def _setup(sources):
    tmp = tempfile.mkdtemp()
    models.manual_dir = lambda model: os.path.join(tmp, model)
    models._sources = lambda: list(sources)
    return os.path.join(tmp, "small")


def _check_files(dst):
    for n in ("model.bin", "config.json"):
        with open(os.path.join(dst, n), "rb") as f:
            assert f.read() == FILES[n], n
    assert not os.path.exists(os.path.join(dst, "README.md"))
    assert not [f for f in os.listdir(dst) if f.endswith(".part")]


def test_endpoints_order_and_dedupe():
    os.environ.pop("HF_ENDPOINT", None)
    eps = models.endpoints()
    assert eps[0] == "https://huggingface.co" and "https://hf-mirror.com" in eps, eps
    os.environ["HF_ENDPOINT"] = "https://my-proxy.example/"
    assert models.endpoints()[0] == "https://my-proxy.example"
    os.environ.pop("HF_ENDPOINT", None)


def test_china_scenario_ends_on_modelscope():
    hf, _sock = blackhole()
    mirror, mlog = serve("hf", "stall_all", stall_after=64 << 10)
    ms, slog = serve("ms")
    dst = _setup([(hf, "hf"), (mirror, "hf"), (ms, "ms")])
    prog = []
    t0 = time.time()
    assert models.download("small", lambda d, t: prog.append((d, t))) is True
    took = time.time() - t0
    _check_files(dst)
    assert took < 8, f"国内场景不该卡: {took:.1f}s"
    assert any("model.bin" in p and r is None for p, r in slog), slog   # 真正下载走的魔搭
    assert prog[0] == (0, 0) and prog[-1][0] == prog[-1][1] > 0, prog[-3:]


def test_overseas_prefers_fastest():
    hf, hlog = serve("hf")
    ms, slog = serve("ms", "slow")
    dst = _setup([(hf, "hf"), (ms, "ms")])
    assert models.download("small") is True
    _check_files(dst)
    assert any(p.endswith("model.bin") and r is None for p, r in hlog)
    assert not any(p.endswith("model.bin") and r is None for p, r in slog)


def test_stall_mid_download_switches_and_resumes():
    a, alog = serve("hf", "stall_full", stall_after=1_000_000)   # 测速快, 正式下载到 1MB 卡住
    b, blog = serve("ms", "medium")
    dst = _setup([(a, "hf"), (b, "ms")])
    assert models.download("small") is True
    _check_files(dst)
    resumed = [r for p, r in blog if p.endswith("model.bin") and r and not r.startswith("bytes=0-")]
    assert resumed and int(resumed[0].split("=")[1].split("-")[0]) >= 900_000, blog


def test_all_sources_down_gives_actionable_message():
    hf, _s = blackhole()
    dst = _setup([(hf, "hf"), (dead(), "hf"), (dead(), "ms")])
    try:
        models.download("small")
        assert False, "应抛 ModelDownloadError"
    except models.ModelDownloadError as e:
        s = str(e)
        assert "models\\small" in s and "model.bin" in s, s
    assert not os.path.exists(os.path.join(dst, "model.bin"))


def test_corrupt_file_rejected():
    bad, _ = serve("ms", "corrupt")
    dst = _setup([(bad, "ms")])
    try:
        models.download("small")
        assert False, "sha256 不对应报错"
    except models.ModelDownloadError as e:
        assert "sha256" in str(e) or "model.bin" in str(e)
    assert not os.path.exists(os.path.join(dst, "model.bin"))
    assert not models.is_ready("small")


def test_partial_file_resumes_next_run():
    ms, slog = serve("ms")
    dst = _setup([(ms, "ms")])
    os.makedirs(dst)
    with open(os.path.join(dst, "model.bin.part"), "wb") as f:
        f.write(BIN[:2_000_000])
    assert models.download("small") is True
    _check_files(dst)
    assert ("/models/%s/resolve/master/model.bin" % REPO, "bytes=2000000-") in slog, slog


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
            t0 = time.time()
            try:
                fn()
                print(f"  ✓ {name}  ({time.time() - t0:.1f}s)")
            except Exception as e:
                fails += 1
                print(f"  ✗✗✗ {name}: {type(e).__name__}: {e}")
    print(f"\n{'❌ 有失败' if fails else '✓ 模型下载多源/续传/校验全部通过'}")
    sys.exit(1 if fails else 0)
