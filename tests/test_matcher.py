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
    ("骑兵冲锋", True),
    # 乱码错听不该乱执行: "冲锋"听成"撤锋", 不能因为有"撤"就当撤退
    ("骑兵撤锋", False),
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
    # 弓骑兵难念 -> 数字定位/稳定错听都能选中第四队(key 4)
    ("第四队冲锋", ["4", "f1", "f3"]),
    ("骑射兵散开", ["4", "f2", "f3"]),
    ("空骑兵上马", ["4", "f5"]),
    # 词序: 攻击动词后的兵种是"打击目标"(敌方), 不是选中对象 —— 选的是动词前那个
    ("骑兵进攻弓箭手", ["3", "f1", "f3"]),
    ("骑兵打他们的弓箭手", ["3", "f1", "f3"]),
    ("步兵进攻骑兵", ["1", "f1", "f3"]),
    # 模组指令(模组不在时退化为冲锋键序); 不能被"打他们/冲"抢路由
    ("骑兵打最近的", ["3", "f1", "f3"]),
    ("全军攻击最近的", ["0", "f1", "f3"]),
    # 目标句式不影响正常句 (进攻是charge的别名; 主语在动词前照常选中)
    ("弓箭手进攻", ["2", "f1", "f3"]),
]
for text, want in KEY_CASES:
    r = m.parse(text)
    keys = None
    if r:
        keys = ([r["group"]["select"]] if r["group"] else []) + r["order"]["keys"]
    mark = "✓" if keys == want else "✗✗✗"
    fails += keys != want
    print(f"  {mark} 「{text}」 -> {keys} (期望 {want})")

# 目标解析专项: 动词后的兵种应记为 target(敌方), 且不被选中
print("\n=== 指向性目标专项 ===")
TARGET_CASES = [
    ("骑兵进攻弓箭手", "cavalry", "archers"),
    ("骑兵打他们的弓箭手", "cavalry", "archers"),
    ("进攻弓箭手", None, "archers"),          # 无主语: 作用于当前选中编队
    ("骑兵冲锋", "cavalry", None),            # 无目标: 普通冲锋
    ("弓箭手进攻", "archers", None),          # 主语在动词前, 不是目标
]
for text, want_g, want_t in TARGET_CASES:
    tr = m.explain(text)
    r = tr["result"]
    got_g = r["group"]["name"] if r and r["group"] else None
    got_t = r["target"]["name"] if r and r.get("target") else None
    ok = r is not None and got_g == want_g and got_t == want_t
    fails += not ok
    print(f"  {'✓' if ok else '✗✗✗'} 「{text}」 -> 选中={got_g} 目标={got_t} "
          f"(期望 选中={want_g} 目标={want_t})")

total = len(SAMPLES) + len(GROUP_CASES) + len(KEY_CASES) + len(TARGET_CASES)
print(f"\n{total - fails}/{total} 通过")
sys.exit(1 if fails else 0)
