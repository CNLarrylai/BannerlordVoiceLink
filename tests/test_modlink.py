# -*- coding: utf-8 -*-
"""modlink 桥的单元测试: 假 TCP 服务器扮演游戏内模组, 验证协议往返与降级。"""
import os
import socket
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from modlink import ModLink  # noqa: E402


def _fake_mod(reply):
    """起一个一次性假模组服务器, 返回 (port, got) — got[0] 是收到的请求行。"""
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    got = [None]

    def run():
        try:
            c, _ = srv.accept()
            # 协议是 UTF-8 (notify 带中文), 假服务器同步
            f = c.makefile("rw", encoding="utf-8", newline="\n")
            got[0] = (f.readline() or "").strip()
            f.write(reply + "\n")
            f.flush()
            c.close()
        finally:
            srv.close()

    threading.Thread(target=run, daemon=True).start()
    return port, got


def test_attack_roundtrip():
    port, got = _fake_mod("ok attacked=1 target=Ranged:80:120")
    r = ModLink(port=port).attack("cavalry", "archers")
    assert r == "ok attacked=1 target=Ranged:80:120", r
    assert got[0] == "attack cavalry archers", got[0]


def test_group_none_becomes_all():
    port, got = _fake_mod("ok attacked=3 target=Cavalry:40:90")
    r = ModLink(port=port).attack(None, "nearest")
    assert r and r.startswith("ok")
    assert got[0] == "attack all nearest", got[0]


def test_err_passthrough():
    port, _ = _fake_mod("err no_battle")
    r = ModLink(port=port).attack("infantry", "nearest")
    assert r == "err no_battle", r


def test_unavailable_returns_none_fast():
    # 拿一个刚释放的端口 => 连接被拒 => None (毫秒级, 不卡语音主流程)
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    import time
    t0 = time.perf_counter()
    r = ModLink(port=port, timeout=0.25).attack("cavalry", "nearest")
    dt = time.perf_counter() - t0
    assert r is None
    assert dt < 1.0, f"降级太慢: {dt:.2f}s"


def test_disabled_noop():
    assert ModLink(port=1, enabled=False).attack("cavalry", "nearest") is None
    assert ModLink(port=1, enabled=False).ping() is None
    assert ModLink(port=1, enabled=False).notify("骑兵 · 冲锋") is None


def test_notify_utf8_roundtrip():
    # 中文描述(含空格)整行到达, 不被按空格截断; UTF-8 编解码往返无损
    port, got = _fake_mod("ok")
    r = ModLink(port=port).notify("全军 · 盾墙 顶住")
    assert r == "ok", r
    assert got[0] == "notify 全军 · 盾墙 顶住", got[0]


def test_split_roundtrip():
    port, got = _fake_mod("ok split=Cavalry a=20 b=20")
    r = ModLink(port=port).split("cavalry")
    assert r and r.startswith("ok split=")
    assert got[0] == "split cavalry", got[0]


def test_sideorder_roundtrip():
    port, got = _fake_mod("ok side=left units=20")
    r = ModLink(port=port).sideorder("left", "charge")
    assert r == "ok side=left units=20", r
    assert got[0] == "sideorder left charge", got[0]


def test_sideorder_not_split_err():
    port, _ = _fake_mod("err not_split")
    r = ModLink(port=port).sideorder("right", "follow")
    assert r == "err not_split", r


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
    print(f"\n{'❌ 有失败' if fails else '✓ modlink 桥全部通过'}")
    sys.exit(1 if fails else 0)
