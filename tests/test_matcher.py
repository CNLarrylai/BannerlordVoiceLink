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
    # 光喊兵种名不执行 —— 曾被"开射"(kaishe)谐音蹭到89分触发自由射击:
    # 兵种"骑射"精确100分占满同一段时, 谐音指令是寄生, 必须让位
    ("骑射", False),
    ("骑射。", False),
    ("提设。", False),   # "骑射"的错听, 同样不该触发开射
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
    # "出击"必须直达冲锋: 不收录时被"护驾"拼音蹭89分错路由成跟随我
    # (2026-07-09 实战连错三次)
    ("全军出击", ["0", "f1", "f3"]),
    ("出击", ["f1", "f3"]),
    # 覆盖优先于精确(口音基准钓出): "停止蛇己"=平翘舌的"停止射击", 整句拼音
    # 全同(覆盖4字)必须赢字面子串"停止"(只覆盖2字), 否则停止射击变立定
    ("停止蛇己", ["f4"]),
    ("停止射击", ["f4"]),
    ("停止", ["f1", "f6"]),          # 光说"停止"仍是立定, 不许被上面带偏
    ("回来", ["f1", "f5"]),          # 实战高频说法直达后退
    # 否定前缀守卫: "开货"(=开火的错听)拼音滑进"别开火"会丢掉"别"→语义反转
    # (想开火变停火)。丢否定字的对齐一律作废; 完整说"别开火"不受影响。
    ("开货", ["f4"]),                # -> fire_at_will 开火
    ("开火", ["f4"]),
    ("别开火", ["f4"]),              # hold_fire 同键位 f4, 靠下面名字断言区分
    # 整句=单字别名必须赢"藏着它的长别名": 喊"冲"是冲锋, 不是"跟我冲"
    ("冲", ["f1", "f3"]),
    ("集火", ["f1", "f3"]),          # 玩家最高频集火说法, 曾漏(只有"集火这只")
    # 弓骑兵难念 -> 数字定位/稳定错听都能选中第四队(key 4)
    ("第四队冲锋", ["4", "f1", "f3"]),
    ("骑射兵散开", ["4", "f2", "f3"]),
    ("空骑兵上马", ["4", "f5"]),
    # 词序: 攻击动词后的兵种是"打击目标"(敌方), 不是选中对象 —— 选的是动词前那个
    ("骑兵进攻弓箭手", ["3", "f1", "f3"]),
    ("步兵进攻骑兵", ["1", "f1", "f3"]),
    # "打他们"=focus_target(集火眼前那支), 键序=f1f3(退化冲锋); 兵种前缀照选
    ("骑兵打他们", ["3", "f1", "f3"]),
    # 目标句式不影响正常句 (进攻是charge的别名; 主语在动词前照常选中)
    ("弓箭手进攻", ["2", "f1", "f3"]),
    # focus_target(打这只=集火玩家最近): 无兵种=当前/全体; 带兵种=该编队集火
    ("集火这只", ["f1", "f3"]),
    ("骑兵打这只", ["3", "f1", "f3"]),
    # 寄生子串抑制: "军队"曾误认成兵种"马队"→骑兵, 现应无兵种(整句是focus_target)
    ("打这只军队", ["f1", "f3"]),
    ("打那只军队", ["f1", "f3"]),
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
    ("骑兵进攻他们的弓箭手", "cavalry", "archers"),
    ("进攻弓箭手", None, "archers"),          # 无主语: 作用于当前选中编队
    ("骑兵冲锋", "cavalry", None),            # 无目标: 普通冲锋
    ("弓箭手进攻", "archers", None),          # 主语在动词前, 不是目标
    # Whisper 连读断句塞的标点(全角冒号/顿号)不能破坏识别: 弓、骑兵 应仍是弓骑兵
    ("弓、骑兵：冲锋：对方：弓、骑兵：。", "horse_archers", "horse_archers"),
    ("骑兵，进攻，弓箭手。", "cavalry", "archers"),
    # 左右半队也能定向进攻: "骑兵左队进攻弓箭手" 选中左半队, 目标敌方弓箭手
    ("骑兵左队进攻弓箭手", "cavalry_left", "archers"),
    ("第五队进攻弓箭手", "form5", "archers"),
    # 同音字替换的精确子串陷阱: "弓骑兵"听成"功骑兵", 拼音满分的整词(盖3字)
    # 必须赢字面藏在里面的"骑兵"(2字) —— 否则打弓骑兵变成打骑兵(实战报告)
    ("骑兵进攻对方功骑兵", "cavalry", "horse_archers"),
    ("骑兵进攻对方弓骑兵", "cavalry", "horse_archers"),
    ("功骑兵冲锋", "horse_archers", None),
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

# 指令名专项: fire_at_will/hold_fire 同为 f4 键, 键序断言分不开, 按名字断言
# (否定前缀守卫: "开货"=开火的错听, 绝不能滑进"别开火"变成停火)
print("\n=== 指令名专项 (同键位反义对) ===")
NAME_CASES = [
    ("开火", "fire_at_will"),
    ("开货", "fire_at_will"),        # 错听形, 否定守卫防滑进"别开火"
    ("别开火", "hold_fire"),
    ("别射了", "hold_fire"),
    ("放箭", "fire_at_will"),
    ("别放箭", "hold_fire"),
]
for text, want in NAME_CASES:
    r = m.parse(text)
    got = r["order"]["name"] if r else None
    ok = got == want
    fails += not ok
    print(f"  {'✓' if ok else '✗✗✗'} 「{text}」 -> {got} (期望 {want})")

# 分队专项: split 指令 + left/right 伪兵种(左右半队指挥)
print("\n=== 分队/左右半队 ===")
SPLIT_CASES = [
    ("骑兵分队", "cavalry", "split"),
    ("步兵一分为二", "infantry", "split"),
    ("弓箭手分成两队", "archers", "split"),
    # 左右半队必须带兵种前缀(左=原队/右=新队), 各兵种独立
    ("骑兵左队进攻", "cavalry_left", "charge"),
    ("骑兵右队跟我", "cavalry_right", "follow_me"),
    ("弓箭手左队待命", "archers_left", "halt"),
    ("步兵右队后退", "infantry_right", "fall_back"),
    ("左路骑兵冲锋", "cavalry_left", "charge"),
    ("骑射右队撤退", "horse_archers_right", "retreat"),
    ("第六队盾墙", "form6", "shield_wall"),
    ("第五队游击", "form5", "skirmish"),
    ("骑兵左队自由射击", "cavalry_left", "fire_at_will"),
    # 复合不能污染光杆兵种: "骑兵冲锋" 仍是 cavalry, 不被 cavalry_left 抢
    ("骑兵冲锋", "cavalry", "charge"),
    # 第N队按槽位号指挥(第五~八队=分队新队落的空槽)
    ("第五队进攻", "form5", "charge"),
    ("第六队跟我", "form6", "follow_me"),
    ("第七队待命", "form7", "halt"),
    ("八队撤退", "form8", "retreat"),
    # 第一~四队仍是兵种别名(走按键), 不被 formN 抢
    ("第一队冲锋", "infantry", "charge"),
    ("第四队散开", "horse_archers", "loose"),
    # 战术层(FormationAI): 绕后=交AI包抄, 听令=收回指挥权
    ("骑兵绕后", "cavalry", "flank"),
    ("骑兵绕到背后", "cavalry", "flank"),
    ("骑射迂回包抄", "horse_archers", "flank"),
    ("全军听令", "all", "reclaim"),
    ("骑兵听令", "cavalry", "reclaim"),
    # 战术层第二批: 占高地/游击/稳步推进/护弓 (2026-09 三方向冲突检索后定稿)
    ("弓箭手占高地", "archers", "hold_high_ground"),
    ("步兵上高地", "infantry", "hold_high_ground"),      # 曾被拼音蹭成上马
    ("全军抢占高地", "all", "hold_high_ground"),          # 曾被蹭成盾墙
    ("骑射游击", "horse_archers", "skirmish"),           # 曾被蹭成骑射右队冲锋
    ("骑兵放风筝", "cavalry", "skirmish"),
    ("步兵稳步推进", "infantry", "cautious_advance"),    # 含"推进"但不被 advance 抢
    ("全军步步为营", "all", "cautious_advance"),
    ("骑兵保护弓箭手", "cavalry", "protect"),
    ("骑兵保护左翼", "cavalry", "guard_left"),
    ("骑兵守住右翼", "cavalry", "guard_right"),
    ("骑射掩护右翼", "horse_archers", "guard_right"),   # "右翼"不能被"游击"抢
    ("骑射游击", "horse_archers", "skirmish"),           # 反向也不能被"右翼"抢
    ("步兵掩护弓箭手", "infantry", "protect"),
    # 不能被新指令抢走的老指令
    ("弓箭手去那", "archers", "to_position"),           # 曾被"护住弓箭手"劫走
    ("友谊", None, None),                               # youyi 曾满分蹭到"护右翼"
    ("有时候有一些换听", None, None),
    ("步兵慢慢推进", "infantry", "advance"),
    ("骑兵攻击对方弓箭手", "cavalry", "charge"),          # 补"攻击"前解析成骑射手左队
]
for text, want_g, want_o in SPLIT_CASES:
    r = m.parse(text)
    gg = r["group"]["name"] if r and r["group"] else None
    oo = r["order"]["name"] if r and r["order"] else None
    ok = gg == want_g and oo == want_o
    fails += not ok
    print(f"  {'✓' if ok else '✗✗✗'} 「{text}」 -> {gg}/{oo} (期望 {want_g}/{want_o})")

print("\n=== 英文模式 (口音容错 / 按词占比 / 短噪音) ===")
m_en = Matcher(commands, settings["control"]["match_threshold"],
               settings["control"].get("chat_filter", True), lang="en")
# (句子, 期望兵种或None, 期望指令或None); 指令 None = 应忽略
EN_CASES = [
    # 2026-09-02 真实日志: 非母语 "All" 尾音吞掉, Whisper 写成 Or/Oh
    ("Or unit charge.", "all", "charge"),
    ("Or unit, follow me.", "all", "follow_me"),
    ("Oh units charge", "all", "charge"),
    ("All units charge.", "all", "charge"),
    ("Everyone, everyone, follow me.", "all", "follow_me"),
    ("Units, charge!", "all", "charge"),
    ("All troops, hold position.", "all", "halt"),
    ("Infantry, shield wall!", "infantry", "shield_wall"),
    ("Archers, fire at will.", "archers", "fire_at_will"),
    ("Cavalry, charge now!", "cavalry", "charge"),
    ("Horse archers, fall back.", "horse_archers", "fall_back"),
    ("Cavalry, flank them.", "cavalry", "flank"),
    ("Infantry, advance.", "infantry", "advance"),
    ("Cavalry, split!", "cavalry", "split"),
    ("Archers, hold the high ground", "archers", "hold_high_ground"),  # 曾被蹭成 halt
    ("All units, take the high ground", "all", "hold_high_ground"),   # 曾被蹭成 flank
    ("Horse archers, skirmish", "horse_archers", "skirmish"),
    ("Horse archers, kite them", "horse_archers", "skirmish"),        # 曾被蹭成集火
    ("Infantry, advance carefully", "infantry", "cautious_advance"),
    ("Infantry, advance cautiously!", "infantry", "cautious_advance"),  # 实测漏收
    ("Archer, skimish!", "archers", "skirmish"),                        # 实测错听
    ("Cavalry, protect the archers", "cavalry", "protect"),
    ("Cavalry, protect the left flank", "cavalry", "guard_left"),
    ("Cavalry, guard the right flank", "cavalry", "guard_right"),
    ("Cavalry, protect left wing!", "cavalry", "guard_left"),      # 实测漏收
    ("Cavalry, protect the horse archers", "cavalry", "protect"),   # 目标=骑射, 主程序放行
    ("Infantry, advance", "infantry", "advance"),
    # Whisper 输出阿拉伯数字: "Group 2" 曾模糊蹭成 group four
    ("Group 2, follow me", "archers", "follow_me"),
    ("Group 4, charge", "horse_archers", "charge"),
    ("Group 5, charge", "form5", "charge"),
    ("Group 7, fall back", "form7", "fall_back"),
    # 第5~8队 / 半队 收全部指令 (2026-09-03 走查: Group 6 skirmish 曾没反应)
    ("Group 6, skirmish", "form6", "skirmish"),
    ("Group 5, shield wall", "form5", "shield_wall"),
    ("Cavalry left, fire at will", "cavalry_left", "fire_at_will"),
    # 2026-09-03 实测错听/漏收
    ("Group 4, Vetch Formation", "horse_archers", "skein"),
    ("Groove 6, charge!", "form6", "charge"),
    ("Infantry, split into two groups.", "infantry", "split"),
    ("Cavalry, flank their archers!", "cavalry", "flank"),
    ("Group 1, Loose Formation.", "infantry", "loose"),
    ("Group 1 lose formation!", "infantry", "loose"),
    ("Archers, spread out.", "archers", "loose"),
    # 一个没解释的词放行(≈中文 2 字余量)
    ("Okay cavalry charge", "cavalry", "charge"),
    # 聊天: 杂词多 -> 忽略
    ("I think the cavalry should charge", None, None),
    ("Did you see how the archers were shooting", None, None),
    # 噪音短句: 不许蹭到任何指令
    ("Or.", None, None),
    ("Oh.", None, None),
    ("So", None, None),
    ("Hmm", None, None),
    # 光喊兵种不执行
    ("Archers.", None, None),
    # 就近集火与中文"打他们"对齐: attack them / get them / kill them -> focus_target;
    # 泛指冲锋 charge/attack/charge them 不变; 带目标的 "attack the archers" 仍是
    # 定向冲锋(不许被 "attack them" 模糊蹭走)
    ("Cavalry, attack them!", "cavalry", "focus_target"),
    ("Attack them", None, "focus_target"),
    ("Get them!", None, "focus_target"),
    ("Kill them", None, "focus_target"),
    ("Attack the nearest enemy", None, "focus_target"),
    ("Cavalry, charge them", "cavalry", "charge"),
    ("Cavalry, attack!", "cavalry", "charge"),
    ("Cavalry attack their archers", "cavalry", "charge"),
    ("Infantry attack the archers", "infantry", "charge"),
]
for text, want_g, want_o in EN_CASES:
    r = m_en.parse(text)
    gg = r["group"]["name"] if r and r["group"] else None
    oo = r["order"]["name"] if r and r["order"] else None
    ok = gg == want_g and oo == want_o
    fails += not ok
    print(f"  {'✓' if ok else '✗✗✗'} 「{text}」 -> {gg}/{oo} (期望 {want_g}/{want_o})")

total = (len(SAMPLES) + len(GROUP_CASES) + len(KEY_CASES) + len(TARGET_CASES)
         + len(NAME_CASES) + len(SPLIT_CASES) + len(EN_CASES))
print(f"\n{total - fails}/{total} 通过")
sys.exit(1 if fails else 0)
