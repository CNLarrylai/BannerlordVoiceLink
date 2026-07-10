# -*- coding: utf-8 -*-
"""口语化说法全扫 —— 词库覆盖检查 + 快路/兜底路由实测。

阶段1 (--text, 秒级): 候选口语说法逐条过 matcher:
  ✓已覆盖(命中正确指令) / ⚠错配(命中了别的指令, 比漏更危险!) / ✗未覆盖。
阶段2 (--audio): 对"最终会在词库里"的说法, TTS(标准+陕西两声线)合成 →
  流式+热词解码 → 判定这条说法实际走快路还是落 Whisper。
  高频说法若总落兜底(慢200ms), 是热词扩容的候选。

候选清单是"玩家可能怎么喊"的头脑风暴, 不是词库本身 ——
危险的日常词(溜了/跑路/挂机…)只测不收, 结论里说明理由。
用法: .venv\\Scripts\\python kws\\colloquial_sweep.py [--text|--audio]
"""
import asyncio
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, HERE)

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

import yaml  # noqa: E402

# 每指令的口语候选 (玩家/主播实际会喊的说法; 含刻意的"危险词"用于验证不收的理由)
CANDIDATES = {
    "charge": ["冲", "冲啊", "上", "都给我上", "干他们", "干上去", "莽上去",
               "怼上去", "冲了", "全冲", "杀过去", "开干", "开团", "A上去",
               "干死他们", "带走他们", "梭哈"],
    "advance": ["往前", "压上", "推上去", "慢慢推", "往前走", "前压", "慢推",
                "推进", "走起"],
    "focus_target": ["打他", "打他们", "集火", "秒他", "先打这个", "搞他",
                     "打这个", "集火他", "盯着这只打", "就打他"],
    "follow_me": ["跟我来", "跟上", "跟紧我", "别掉队", "来我这", "到我身边",
                  "跟我走", "护驾", "都跟着我"],
    "halt": ["停", "站住", "别动", "原地待命", "停停停", "先别动", "都站住",
             "别走", "待命"],
    "fall_back": ["退", "后退", "回来", "撤", "往后撤", "退一点", "回防",
                  "退回去", "往回走", "别上"],
    "retreat": ["撤退", "快跑", "撤了", "快撤", "全军撤退", "跑路", "溜了",
                "别打了快跑", "逃"],
    "to_position": ["来这", "过来", "去那", "去那个位置", "守在这", "过来这边",
                    "站到那边"],
    "line": ["一字排开", "横排", "拉开线", "站成一排", "排开", "列队"],
    "shield_wall": ["举盾", "龟起来", "组盾墙", "把盾举起来", "盾牌举起来",
                    "缩起来"],
    "loose": ["散开", "别扎堆", "拉开", "散一点", "别挤", "分散开", "拉开点"],
    "circle": ["围成圈", "抱团", "围一圈", "圈起来", "围起来"],
    "square": ["方阵", "站成方块", "口字阵"],
    "skein": ["三角阵", "楔形", "尖刀阵", "箭头阵"],
    "column": ["排成一列", "竖排", "一路纵队", "排队", "排成一行"],
    "scatter": ["乱阵", "随便站", "自由站位", "打乱队形"],
    "fire_at_will": ["放箭", "开火", "射击", "自由开火", "给我射", "射他们",
                     "火力全开", "射起来"],
    "hold_fire": ["别射", "停火", "别放箭", "省着点箭", "收手", "先别射",
                  "别射了"],
    "mount_toggle": ["上马", "下马", "都上马", "翻身上马", "骑上马"],
    "ai_control": ["交给AI", "自己打", "你们自己来", "自由发挥", "托管",
                   "挂机", "不用管了"],
    "face_direction": ["朝这边", "看这边", "面向这边", "转过来", "朝我这边"],
    "retreat2": [],  # 占位防笔误
}
CANDIDATES.pop("retreat2")

VOICES = [("标准女", "zh-CN-XiaoxiaoNeural"), ("陕西", "zh-CN-shaanxi-XiaoniNeural")]
AUD = os.path.join(HERE, "audio_colloquial")


def build():
    import dictionary
    from matcher import Matcher
    cfg = yaml.safe_load(open(os.path.join(ROOT, "config", "settings.yaml"),
                              encoding="utf-8"))
    cmds = dictionary.load_commands()
    m = Matcher.from_config(cmds, cfg["control"], lang="zh")
    return cfg, cmds, m


def stage_text():
    _cfg, _cmds, m = build()
    covered, mismatch, missing = [], [], []
    for key, exprs in CANDIDATES.items():
        for e in exprs:
            r = m.parse(e)
            got = r["order"]["name"] if r and r.get("order") else None
            if got == key:
                covered.append((e, key, r["order"]["score"]))
            elif got:
                mismatch.append((e, key, got))
            else:
                missing.append((e, key))
    print(f"===== 阶段1: 词库覆盖 ({sum(len(v) for v in CANDIDATES.values())} 条候选) =====")
    print(f"\n⚠ 错配 {len(mismatch)} 条 (说A执行B, 最危险):")
    for e, want, got in mismatch:
        print(f"  「{e}」 想要 {want} → 实际 {got}")
    print(f"\n✗ 未覆盖 {len(missing)} 条:")
    for e, want in missing:
        print(f"  「{e}」 → {want}")
    print(f"\n✓ 已覆盖 {len(covered)} 条 (低于90分的列出, 属'惊险接住'):")
    for e, want, sc in covered:
        if sc < 90:
            print(f"  「{e}」 → {want} ({round(sc)}分)")


def stage_audio():
    import numpy as np
    import stream_asr
    from stt import Transcriber
    from bench_accents import load_mp3
    cfg, cmds, m = build()
    cfg["stt"]["language"] = "zh"

    # 只测"词库里能接住"的说法 (路由问题只对已覆盖说法有意义)
    tests = []
    for key, exprs in CANDIDATES.items():
        for e in exprs:
            r = m.parse(e)
            if r and r.get("order") and r["order"]["name"] == key:
                tests.append((e, key))
    print(f"===== 阶段2: 快路/兜底路由 ({len(tests)} 条已覆盖说法 × {len(VOICES)} 声线) =====")

    async def synth():
        import edge_tts
        for _vn, vid in VOICES:
            os.makedirs(os.path.join(AUD, vid), exist_ok=True)
            for e, _k in tests:
                h = hashlib.md5(e.encode()).hexdigest()[:10]
                p = os.path.join(AUD, vid, f"{h}.mp3")
                if not os.path.exists(p) or os.path.getsize(p) < 500:
                    await edge_tts.Communicate(e, vid).save(p)
    asyncio.run(synth())

    print("加载引擎…")
    stream = stream_asr.make_stream(stream_asr.build_hotwords(cmds))
    tr = Transcriber(cfg)
    orders = set(cmds["orders"])

    rows = []          # (expr, key, voice, route, ok)
    for vn, vid in VOICES:
        for e, key in tests:
            h = hashlib.md5(e.encode()).hexdigest()[:10]
            s = load_mp3(os.path.join(AUD, vid, f"{h}.mp3"))
            stext = stream_asr.transcribe(stream, s, 16000)
            r = m.parse(stext)
            skey = r["order"]["name"] if r and r.get("order") else None
            if skey:                       # 快路解出指令 => 直出
                rows.append((e, key, vn, "快路", skey == key, stext))
                continue
            wtext = tr.transcribe(s)
            r = m.parse(wtext)
            wkey = r["order"]["name"] if r and r.get("order") else None
            rows.append((e, key, vn, "兜底", wkey == key, wtext))

    # 汇总: 每条说法的路由画像
    print(f"\n{'说法':<10s} {'指令':<14s} {'标准女':<12s} {'陕西':<12s}")
    stat = {"快路✓": 0, "兜底✓": 0, "✗": 0}
    by_expr = {}
    for e, key, vn, route, ok, heard in rows:
        tag = f"{route}{'✓' if ok else '✗'}"
        if not ok:
            tag += f"「{heard[:6]}」"
        by_expr.setdefault((e, key), {})[vn] = tag
        stat["✗" if not ok else f"{route}✓"] += 1
    for (e, key), r in by_expr.items():
        print(f"「{e}」".ljust(12) + key.ljust(14)
              + r.get("标准女", "-").ljust(14) + r.get("陕西", "-"))
    n = len(rows)
    print(f"\n合计: 快路直出 {stat['快路✓']}/{n}  落兜底但接住 {stat['兜底✓']}/{n}  "
          f"全挂 {stat['✗']}/{n}")
    print("\n→ 高频说法若稳定落兜底, 是热词扩容候选; 全挂的要么改词库要么放弃。")


if __name__ == "__main__":
    if "--audio" in sys.argv:
        stage_audio()
    else:
        stage_text()
