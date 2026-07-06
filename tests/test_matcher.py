"""匹配回归测试 (纯文本, 不需要麦克风/显卡, 秒级)。

验证: 指令解析、聊天过滤、全军编队、按键序列。
断言不符会以非零码退出 (可接入 CI / run_all.py)。
"""
import os
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import yaml  # noqa: E402
from matcher import Matcher  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(ROOT, "config", "settings.yaml"), encoding="utf-8") as f:
    settings = yaml.safe_load(f)
with open(os.path.join(ROOT, "config", "commands.yaml"), encoding="utf-8") as f:
    commands = yaml.safe_load(f)

m = Matcher(commands, settings["control"]["match_threshold"],
            settings["control"].get("chat_filter", True))

# (句子, 是否应该执行)
SAMPLES = [
    # ---- 真指令, 应执行 ----
    ("弓箭手散开", True),
    ("让弓兵疏散队形", True),
    ("步兵盾墙", True),
    ("全军冲锋", True),
    ("全军突击!", True),
    ("士兵冲锋。", True),
    ("骑兵给我冲上去", True),
    ("弓箭手自由射击", True),
    ("所有人停下", True),
    ("骑射手跟着我", True),
    ("盾兵结盾阵顶住", True),
    ("弓箭手全部给我散开!", True),
    ("士兵们快来护驾!", True),
    ("护驾!", True),
    # ---- "全军"口语都要选中 all, 不能落到当前兵种 ----
    ("所有人跟随我", True),
    ("大家跟我上", True),
    ("大伙儿冲锋", True),
    ("全体停下", True),
    # ---- 聊天(用户实测误触日志), 不应执行 ----
    ("他能够检测到了。", False),
    ("OK,嗯……", False),
    ("你怎么这么慢呢?", False),
    ("全军突击,士兵冲锋。你怎么能听到一些,听不到一些的呢?", False),
    ("是因为声音太多了吗?", False),
    ("呃,对啊,你怎么一时时快时慢的呢?", False),
    ("诶,我发现如果有回音的时候你就检测不准了。", False),
    ("哦,但是你的语音识别的效果还真不错。", False),
    ("然后如果我在说一句话的时候,比如说全军突击这样,插一句那个语音。", False),
    ("哦,那也就是说,可能会有一种情况就是如果我在跟大家聊,这个东西是怎么生效的。", False),
    ("然后里面带了这种士兵冲锋的指令。", False),
    ("士兵冲锋真的很帅", False),
    ("今天天气真好", False),
]


def show(text, expect):
    r = m.parse(text)
    got = r is not None
    mark = "✓" if got == expect else "✗✗✗"
    if r:
        g, o = r["group"], r["order"]
        gs = f"{g['name']}({g['select']})" if g else "—"
        os_ = f"{o['name']}({'+'.join(o['keys'])})"
        print(f"  {mark} 执行[兵种:{gs} 指令:{os_}]  「{text}」")
    else:
        print(f"  {mark} 忽略  「{text}」")
    return got == expect


print("=== 匹配 + 聊天过滤 ===")
fails = sum(0 if show(t, e) else 1 for t, e in SAMPLES)

print("\n=== 全军编队解析专项 ===")
GROUP_CASES = [
    ("所有人跟随我", "all"), ("大家跟我上", "all"), ("大伙儿冲锋", "all"),
    ("全体停下", "all"), ("弓箭手散开", "archers"), ("骑兵冲锋", "cavalry"),
]
for text, want in GROUP_CASES:
    r = m.parse(text)
    got = r["group"]["name"] if r and r["group"] else None
    mark = "✓" if got == want else "✗✗✗"
    fails += got != want
    print(f"  {mark} 「{text}」 -> 兵种 {got} (期望 {want})")

# 键序: 队形在 F2 子菜单(不是 F3!), 盾墙/线阵用顶层 F8/F9。防键位回退。
print("\n=== 按键序列专项 ===")
KEY_CASES = [
    ("步兵盾墙", ["1", "f8"]),
    ("弓箭手线阵", ["2", "f9"]),
    ("骑兵楔阵", ["3", "f2", "f6"]),
    ("全军散阵", ["0", "f2", "f3"]),
    ("步兵前进", ["1", "f1", "f4"]),
    ("弓箭手自由射击", ["2", "f4"]),
    ("骑兵上马", ["3", "f5"]),
    ("步兵举盾牌", ["1", "f8"]),
    ("弓箭手放箭啊", ["2", "f4"]),
    ("大伙儿围成圈", ["0", "f2", "f4"]),
    ("骑兵给我上啊", ["3", "f1", "f3"]),
    ("弓箭手往后退点儿", ["2", "f1", "f5"]),
    ("步兵都别动", ["1", "f1", "f6"]),
    ("步兵三角阵", ["1", "f2", "f6"]),
    ("弓箭手竖排", ["2", "f2", "f7"]),
    ("全军排成一列", ["0", "f2", "f7"]),
]
for text, want in KEY_CASES:
    r = m.parse(text)
    keys = None
    if r:
        keys = ([r["group"]["select"]] if r["group"] else []) + r["order"]["keys"]
    mark = "✓" if keys == want else "✗✗✗"
    fails += keys != want
    print(f"  {mark} 「{text}」 -> {keys} (期望 {want})")

total = len(SAMPLES) + len(GROUP_CASES) + len(KEY_CASES)
print(f"\n{total - fails}/{total} 通过")
sys.exit(1 if fails else 0)
