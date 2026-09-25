# -*- coding: utf-8 -*-
"""编队名册 + 缺队拒发 测试。

锁定 2026-09-25 查实的两个坑(起因: YouTube 用户报 "archers 和 cavalry 反了"):
  ① 数字键是槽位号, 玩家在"战斗部署"里换过顺序时, 词典写死的 1/2/3/4 会指挥错人
     -> 必须按模组名册给的真实键发。
  ② 按一个没兵的槽的键, 游戏会选中**全军**
     -> 名册说没有这支队时, 一个键都不许发。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import roster as rosters  # noqa: E402


class _FakeLink:
    """假模组: roster 回固定名册, select 记账。"""
    def __init__(self, reply, select_ok=True):
        self.reply = reply
        self.select_ok = select_ok
        self.rosters = 0
        self.selected = []

    def roster(self):
        self.rosters += 1
        return self.reply

    def select(self, group):
        self.selected.append(group)
        return "ok 2:40" if self.select_ok else "err group_empty"


DEFAULT = ("ok infantry=1:120:i120 archers=2:75:r75 "
           "cavalry=3:40:c40 horse_archers=-")
# 玩家把骑兵放进 2 号槽、弓箭手放进 3 号槽 (战斗部署里换过顺序)
SWAPPED = ("ok infantry=1:120:i120 archers=3:75:r75 "
           "cavalry=2:40:c40 horse_archers=-")


def test_parses_default_layout():
    r = rosters.Roster(_FakeLink(DEFAULT))
    assert r.resolve("archers") == (rosters.OK, "2", 75, "r75")
    assert r.resolve("cavalry") == (rosters.OK, "3", 40, "c40")


def test_swapped_layout_gives_real_keys():
    r = rosters.Roster(_FakeLink(SWAPPED))
    assert r.resolve("archers")[1] == "3"     # 不是词典里的 2
    assert r.resolve("cavalry")[1] == "2"     # 不是词典里的 3


def test_missing_group_is_missing_not_unknown():
    r = rosters.Roster(_FakeLink(DEFAULT))
    st, key, n, _ = r.resolve("horse_archers")
    assert st == rosters.MISSING and key is None and n == 0


def test_no_mod_or_no_battle_is_unknown():
    for link in (None, _FakeLink("err no_battle"), _FakeLink(None)):
        r = rosters.Roster(link)
        assert r.resolve("archers")[0] == rosters.UNKNOWN


def test_garbled_reply_is_unknown_not_wrong_key():
    """协议对不上时宁可当"未知"(维持老行为), 绝不半懂半猜地发键。"""
    for bad in ("ok archers", "ok archers=x:y:z", "ok =2:3:i3"):
        r = rosters.Roster(_FakeLink(bad))
        assert r.resolve("archers")[0] == rosters.UNKNOWN, bad


def test_cached_within_ttl_then_refetched():
    link = _FakeLink(DEFAULT)
    r = rosters.Roster(link, ttl=99)
    for _ in range(5):
        r.resolve("archers")
    assert link.rosters == 1               # 一条指令一次查询就够
    r.invalidate()
    r.resolve("archers")
    assert link.rosters == 2               # 进出战斗/分队后重取


def test_line_is_readable():
    r = rosters.Roster(_FakeLink(DEFAULT))
    s = r.line()
    assert "archers=键2(75人 r75)" in s and "horse_archers=无" in s
    assert "名册未知" in rosters.Roster(None).line()


# ---------- App._select_group / _no_such_group 的门禁 ----------

class _App:
    """只测选队门禁, 不构造整个 App (避免加载模型/音频)。"""
    from main import App
    _select_group = App._select_group
    _no_such_group = App._no_such_group

    def __init__(self, link, mod_select=True, commands=None):
        self.modlink = link
        self.roster = rosters.Roster(link)
        self.mod_select = mod_select
        self.dry_run = False
        self.lang = "zh"
        self.commands = commands or {"groups": {"cavalry": {"aliases": ["骑兵"]}}}
        self.notified = []
        self.fast = None
        self.idled = 0

    def _debug(self, text):
        pass

    def _idle(self, detail=""):
        self.idled += 1


def test_missing_group_refuses_to_send_any_key():
    a = _App(_FakeLink(DEFAULT))
    assert a._select_group("horse_archers") is None      # None = 拒发


def test_swapped_layout_without_mod_select_presses_real_key():
    a = _App(_FakeLink(SWAPPED), mod_select=False)
    skip, key = a._select_group("archers")
    assert skip is False and key == "3"


def test_mod_select_skips_the_number_key():
    link = _FakeLink(SWAPPED)
    a = _App(link)
    skip, key = a._select_group("archers")
    assert skip is True and key is None
    assert link.selected == ["archers"]


def test_mod_select_failure_falls_back_to_real_key():
    a = _App(_FakeLink(SWAPPED, select_ok=False))
    skip, key = a._select_group("archers")
    assert skip is False and key == "3"


def test_all_and_unknown_keep_old_behaviour():
    a = _App(_FakeLink(DEFAULT))
    assert a._select_group("all") == (False, None)       # 全军键 0 本来就安全
    assert a._select_group(None) == (False, None)
    b = _App(_FakeLink("err no_battle"))
    assert b._select_group("cavalry") == (False, None)   # 名册未知 -> 原样发


def test_no_such_group_tells_the_player_in_game():
    import i18n
    i18n.set_lang("zh")

    class _L(_FakeLink):
        def __init__(self):
            _FakeLink.__init__(self, DEFAULT)
            self.notes = []

        def notify(self, text):
            self.notes.append(text)
            return "ok"

    link = _L()
    a = _App(link)
    import usage                      # 不往用户真的 usage.csv 里写测试行
    real, usage.record = usage.record, lambda *a, **k: None
    try:
        a._no_such_group("cavalry", "charge", "骑兵·冲锋", "骑兵冲锋", 0.1, "")
    finally:
        usage.record = real
    assert len(link.notes) == 1 and "骑兵" in link.notes[0], link.notes
    assert a.idled == 1


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
    print(f"\n{'❌ 有失败' if fails else '✓ 编队名册/缺队拒发 全部通过'}")
    sys.exit(1 if fails else 0)
