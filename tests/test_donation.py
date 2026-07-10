# -*- coding: utf-8 -*-
"""语音数据共建测试 —— 采集规则/导出/作者侧归集 全链路 (秒级)。"""
import json
import os
import sys
import tempfile
import zipfile

import numpy as np

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import donation  # noqa: E402

fails = 0


def check(name, cond):
    global fails
    fails += not cond
    print(f"  {'✓' if cond else '✗✗✗'} {name}")


AUDIO = np.zeros(16000, dtype="float32")

# 全程在临时目录里跑, 不碰真实 %LOCALAPPDATA%
tmp = tempfile.mkdtemp()
ddir = os.path.join(tmp, "donation")
os.makedirs(ddir)
donation.donation_dir = lambda: ddir

print("=== 采集规则 ===")
d_off = donation.Donation({"data_donation": {"enabled": False}})
d_off.save(AUDIO, 16000, "ok", "all", "charge", "全军冲锋", "快路")
check("默认关: 不落任何文件", not os.listdir(ddir))

d_on = donation.Donation({"data_donation": {"enabled": True}})
d_on.save(AUDIO, 16000, "ok", "all", "charge", "全军冲锋", "快路")
wavs = [f for f in os.listdir(ddir) if f.endswith(".wav")]
check("开启后: 执行片段落盘", len(wavs) == 1)
with open(os.path.join(ddir, "manifest.jsonl"), encoding="utf-8") as f:
    rec = json.loads(f.readline())
check("清单含标注", rec["order"] == "charge" and rec["text"] == "全军冲锋")
check("清单含匿名指纹", len(rec["speaker"]) == 16)

d_on.save(AUDIO, 16000, "miss", None, None, "随便聊聊天", "快路")
wavs = [f for f in os.listdir(ddir) if f.endswith(".wav")]
check("未匹配(可能是聊天): 默认不存", len(wavs) == 1)

d_cap = donation.Donation({"data_donation": {"enabled": True, "max_mb": 0}})
d_cap.save(AUDIO, 16000, "ok", None, "halt", "停下", "快路")
wavs = [f for f in os.listdir(ddir) if f.endswith(".wav")]
check("到达上限: 停止保存", len(wavs) == 1)

print("\n=== 导出 ===")
n, mb = donation.stats()
check("统计条数", n == 1)
zp = donation.export_zip()
check("导出 zip 存在", zp and os.path.exists(zp))
with zipfile.ZipFile(zp) as z:
    names = set(z.namelist())
check("zip 含 清单+元信息+wav",
      "manifest.jsonl" in names and "meta.json" in names
      and any(x.startswith("wav/") for x in names))

print("\n=== 作者侧归集 (ingest_donations) ===")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import ingest_donations as ing  # noqa: E402
corpus = os.path.join(tmp, "corpus")
ing.CORPUS = corpus
ing.MANIFEST = os.path.join(corpus, "manifest.jsonl")
os.makedirs(corpus)
seen = ing._load_seen()
with open(ing.MANIFEST, "a", encoding="utf-8") as mf:
    a1, s1 = ing.ingest_zip(zp, seen, mf)
    a2, s2 = ing.ingest_zip(zp, seen, mf)   # 重复导入同一包
check("首次收入 1 条", a1 == 1)
check("重复包全部去重", a2 == 0 and s2 == 1)
spk = [d for d in os.listdir(corpus) if os.path.isdir(os.path.join(corpus, d))]
check("按说话人分目录", len(spk) == 1 and len(spk[0]) == 8)

if fails:
    print(f"\n❌ {fails} 个失败")
    sys.exit(1)
print("\n✓ 语音数据共建全部通过")
