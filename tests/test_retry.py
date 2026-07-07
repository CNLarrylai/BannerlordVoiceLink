# -*- coding: utf-8 -*-
"""重试助推 + 回声抑制的单元测试 (纯逻辑, 用注入的时间, 不碰真时钟)。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from matcher import Matcher  # noqa: E402
from retry import RetryMemory  # noqa: E402

# ---------- RetryMemory 逻辑 ----------


def _mem(**kw):
    kw.setdefault("window_sec", 8.0)
    kw.setdefault("cooldown_sec", 2.5)
    kw.setdefault("bonus", 12)
    return RetryMemory(**kw)


def test_boost_after_similar_retry():
    m = _mem()
    m.note_miss("or units charge", {"all": "all units"}, {}, now=100.0)
    boost, why = m.boost_for("or unit charge", now=103.0)
    assert boost == {"groups": {"all": 12}, "orders": {}}
    assert "重说" in why


def test_no_boost_when_dissimilar():
    m = _mem()
    m.note_miss("all units charge", {"all": "all units"}, {}, now=100.0)
    # 实测无关闲聊相似度最高 ~46 (wow that was a nice hit), 门槛 60 应全拦
    for chat in ("wow that was a nice hit", "that was so cool man",
                 "lets go to the next battle"):
        boost, _ = m.boost_for(chat, now=101.0)
        assert boost is None, chat


def test_boost_for_real_retry_variants():
    m = _mem()
    m.note_miss("or units charge", {"all": "all units"}, {}, now=100.0)
    # 实测真重试(含再次听岔) 75+ 分, 门槛 60 应全放行
    for retry in ("all units charge", "or unit charge"):
        boost, _ = m.boost_for(retry, now=101.0)
        assert boost, retry
    mz = _mem()
    mz.note_miss("全军冲缝", {}, {"charge": "冲锋"}, now=100.0)
    boost, _ = mz.boost_for("全军冲锋", now=101.0)
    assert boost == {"groups": {}, "orders": {"charge": 12}}


def test_no_boost_after_window():
    m = _mem()
    m.note_miss("or units charge", {"all": "all units"}, {}, now=100.0)
    boost, _ = m.boost_for("all units charge", now=109.0)  # 9s > 8s 窗口
    assert boost is None


def test_hotwords_within_window_only():
    m = _mem()
    m.note_miss("x", {"all": "all units"}, {"halt": "stay here"}, now=100.0)
    assert m.hotwords(now=104.0) == "all units, stay here"
    assert m.hotwords(now=120.0) is None


def test_exec_clears_miss():
    m = _mem()
    m.note_miss("or units charge", {"all": "all units"}, {}, now=100.0)
    m.note_exec("all", "charge", now=101.0)
    boost, _ = m.boost_for("all units charge", now=102.0)
    assert boost is None  # 已执行成功, 不再放大


def test_echo_suppressed_within_cooldown():
    m = _mem()
    m.note_exec("all", "charge", now=100.0)
    assert m.is_echo("all", "charge", now=101.5)
    assert not m.is_echo("all", "charge", now=103.0)   # 过了冷却
    assert not m.is_echo("infantry", "charge", now=101.0)  # 不同兵种
    assert not m.is_echo("all", "retreat", now=101.0)      # 不同指令


def test_group_none_treated_as_distinct():
    m = _mem()
    m.note_exec(None, "charge", now=100.0)
    assert m.is_echo(None, "charge", now=101.0)
    # 兵种从 None 变 all (重试放大后过线) => 不是回声, 应执行
    assert not m.is_echo("all", "charge", now=101.0)


def test_disabled_noop():
    m = _mem(enabled=False)
    m.note_miss("x", {"all": "all units"}, {}, now=100.0)
    assert m.boost_for("x", now=101.0) == (None, "")
    assert m.hotwords(now=101.0) is None
    m.note_exec("all", "charge", now=100.0)
    assert not m.is_echo("all", "charge", now=101.0)


def test_empty_miss_not_recorded():
    m = _mem()
    m.note_miss("garbage text", {}, {}, now=100.0)  # 没有够得着的候选
    assert m.boost_for("garbage text", now=101.0) == (None, "")


# ---------- Matcher 定向加分 ----------

CMDS = {
    "groups": {"all": {"key": "0", "aliases": ["全军"], "en": ["everyone"]}},
    "orders": {
        "charge": {"keys": ["f1", "f3"], "aliases": ["冲锋"], "en": ["charge"]},
        "retreat": {"keys": ["f1", "f7"], "aliases": ["撤退"], "en": ["retreat"]},
    },
}


def _strict_matcher():
    # 阈值 101 = 不加分谁也过不了线, 干净地验证 boost 的作用与指向性
    return Matcher(CMDS, threshold=101, chat_filter=False, pinyin_match=False,
                   group_threshold=60, order_threshold=101)


def test_boost_lets_target_pass():
    m = _strict_matcher()
    assert m.parse("全军冲锋") is None
    r = m.parse("全军冲锋", boost={"orders": {"charge": 12}})
    assert r and r["order"]["name"] == "charge"


def test_boost_only_affects_target_key():
    m = _strict_matcher()
    # 加分给的是 retreat, 对句子里的 charge 没帮助 => 仍不执行
    assert m.parse("全军冲锋", boost={"orders": {"retreat": 12}}) is None


def test_boost_none_is_noop():
    m = Matcher(CMDS, threshold=70, chat_filter=False, pinyin_match=False,
                group_threshold=60, order_threshold=70)
    a = m.explain("全军冲锋")
    b = m.explain("全军冲锋", boost=None)
    assert a["result"] and b["result"]
    assert a["order"]["score"] == b["order"]["score"]


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
    print(f"\n{'❌ 有失败' if fails else '✓ 重试助推/回声抑制全部通过'}")
    sys.exit(1 if fails else 0)
