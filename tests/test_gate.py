# -*- coding: utf-8 -*-
"""监听门逻辑测试: 手动开关 + 战斗自动门 的组合。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class _App:
    """只测门逻辑, 不构造整个 App(避免加载模型/音频)。"""
    from main import App
    _gate_open = App._gate_open
    _toggle_listen = App._toggle_listen
    _announce_listen = App._announce_listen
    _listen_state_text = App._listen_state_text
    _battle_poll = App._battle_poll

    def __init__(self, auto_gate, modlink=None, mode="toggle"):
        self.auto_battle_gate = auto_gate
        self.listen_on = True
        self.battle_on = not auto_gate
        self.toggle_key = "left alt"
        self.mode = mode
        self.modlink = modlink
        self.dry_run = False
        self.running = True
        self._notify_q = None
        # _battle_poll 会让编队名册失效(换了一场战斗编队全变), 这里只需个假的
        import roster as rosters
        self.roster = rosters.Roster(None)

    def _idle(self, detail=""):
        pass


def test_no_gate_default_open():
    a = _App(auto_gate=False)
    assert a._gate_open()          # 不开自动门, 默认开着
    a._toggle_listen()
    assert not a._gate_open()      # 手动关 -> 关
    a._toggle_listen()
    assert a._gate_open()          # 再按 -> 开


def test_battle_gate_mutes_outside_battle():
    a = _App(auto_gate=True)
    assert not a._gate_open()      # 开自动门, 初始不在战斗 -> 静音
    a.battle_on = True             # 模组报进入战斗
    assert a._gate_open()          # -> 开
    a.battle_on = False
    assert not a._gate_open()      # 离开战斗 -> 静音


def test_manual_off_overrides_battle():
    a = _App(auto_gate=True)
    a.battle_on = True             # 在战斗中
    assert a._gate_open()
    a._toggle_listen()             # 但手动关掉
    assert not a._gate_open()      # 手动关优先, 静音


class _FakeMod:
    """本机假模组: 收 notify / 回 ping, 记下收到的每一行。"""
    def __init__(self):
        import socket
        import threading
        self.lines = []
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(20)
        self.port = self.sock.getsockname()[1]
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        while True:
            try:
                c, _ = self.sock.accept()
            except OSError:
                return
            with c:
                line = c.makefile("r", encoding="utf-8").readline().strip()
                self.lines.append(line)
                c.sendall(b"ok\n")

    def notifies(self):
        return [x[7:] for x in self.lines if x.startswith("notify ")]


def _wait(cond, secs=3.0):
    import time
    t0 = time.time()
    while time.time() - t0 < secs:
        if cond():
            return True
        time.sleep(0.05)
    return False


def test_toggle_state_pushed_into_game_in_order():
    import i18n
    i18n.set_lang("zh")     # 断言按中文写; 本机配置可能是英文
    from modlink import ModLink
    mod = _FakeMod()
    a = _App(auto_gate=False, modlink=ModLink(port=mod.port))
    a.listen_on = False                 # 按键模式启动是关的
    a._toggle_listen()                  # 开
    a._toggle_listen()                  # 关
    assert _wait(lambda: len(mod.notifies()) == 2), mod.lines
    on, off = mod.notifies()
    assert "开启" in on and "Left Alt" in on and "关闭" in on, on   # "已开启 · 轻点 Left Alt 关闭"
    assert "已关闭" in off and "Left Alt" in off, off
    a.running = False


def test_entering_battle_announces_state_once():
    import i18n
    i18n.set_lang("zh")
    import time
    from modlink import ModLink
    mod = _FakeMod()
    a = _App(auto_gate=False, modlink=ModLink(port=mod.port))
    a.listen_on = False
    a._battle_poll()                    # 假模组在线 = 已在战斗中 -> 补报一次
    assert _wait(lambda: len(mod.notifies()) == 1), mod.lines
    time.sleep(2.5)                     # 再轮询一轮: 仍在战斗, 不重复报
    assert len(mod.notifies()) == 1, mod.notifies()
    assert "已关闭" in mod.notifies()[0]
    a.running = False


def test_continuous_mode_never_announces():
    from modlink import ModLink
    mod = _FakeMod()
    a = _App(auto_gate=True, modlink=ModLink(port=mod.port), mode="continuous")
    a._battle_poll()
    assert _wait(lambda: a.battle_on)   # 自动门照常工作
    import time
    time.sleep(0.3)
    assert mod.notifies() == [], mod.notifies()
    a.running = False


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
    print(f"\n{'❌ 有失败' if fails else '✓ 监听门逻辑全部通过'}")
    sys.exit(1 if fails else 0)
