# -*- coding: utf-8 -*-
"""归集粉丝发来的语音数据包 -> 微调语料库 + 就绪度统计。

用法: .venv/Scripts/python tools/ingest_donations.py <zip或目录> [更多...]
  - 参数是 zip: 直接并入; 是目录: 收该目录下所有 *.zip
  - 语料库: data/corpus/<说话人8位>/... (按匿名机器指纹分说话人)
  - 清单合并到 data/corpus/manifest.jsonl (去重: 说话人+文件名)
  - 最后打印: 总条数/总时长/说话人数/每指令覆盖度 —— 判断"够不够微调"

微调就绪度参考: >=10说话人 且 >=3000条 且 每个常用指令>=100条。
"""
import glob
import json
import os
import sys
import zipfile

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CORPUS = os.path.join(ROOT, "data", "corpus")
MANIFEST = os.path.join(CORPUS, "manifest.jsonl")


def _load_seen():
    seen = set()
    if os.path.exists(MANIFEST):
        with open(MANIFEST, encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                    seen.add((r.get("speaker", ""), r.get("file", "")))
                except Exception:
                    pass
    return seen


def ingest_zip(path, seen, mf):
    added = skipped = 0
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        if "manifest.jsonl" not in names:
            print(f"  !! {os.path.basename(path)} 缺 manifest.jsonl, 跳过")
            return 0, 0
        try:
            meta = json.loads(z.read("meta.json"))
        except Exception:
            meta = {}
        speaker = meta.get("speaker", "unknown")
        spk_dir = os.path.join(CORPUS, speaker[:8])
        os.makedirs(spk_dir, exist_ok=True)
        for line in z.read("manifest.jsonl").decode("utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            rec["speaker"] = speaker            # 以包的指纹为准
            key = (speaker, rec.get("file", ""))
            wav = f"wav/{rec.get('file', '')}"
            if key in seen or wav not in names:
                skipped += 1
                continue
            with open(os.path.join(spk_dir, rec["file"]), "wb") as f:
                f.write(z.read(wav))
            rec["app_pack"] = meta.get("app", "")
            mf.write(json.dumps(rec, ensure_ascii=False) + "\n")
            seen.add(key)
            added += 1
        # 校准录音: 原样收进 calibration 子目录 (新版带 labels.csv 逐条标注;
        # 旧版无标注, 文件名即题号)
        for n in names:
            if n.startswith("calibration/") and n.endswith((".wav", ".csv")):
                cdir = os.path.join(spk_dir, "calibration")
                os.makedirs(cdir, exist_ok=True)
                dst = os.path.join(cdir, os.path.basename(n))
                if not os.path.exists(dst):
                    with open(dst, "wb") as f:
                        f.write(z.read(n))
    return added, skipped


def report():
    rows = []
    with open(MANIFEST, encoding="utf-8") as f:
        for line in f:
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    if not rows:
        print("语料库为空。")
        return
    total_sec = 0.0
    try:
        import soundfile as sf
        for r in rows:
            p = os.path.join(CORPUS, r["speaker"][:8], r["file"])
            if os.path.exists(p):
                info = sf.info(p)
                total_sec += info.frames / info.samplerate
    except Exception:
        pass
    speakers = {r["speaker"] for r in rows}
    from collections import Counter
    per_cmd = Counter(r.get("order") or "(纯兵种)" for r in rows
                      if r.get("result") == "ok")
    print(f"\n===== 语料库就绪度 =====")
    print(f"  条数: {len(rows)}   时长: {total_sec/60:.1f} 分钟   "
          f"说话人: {len(speakers)}")
    print(f"  目标参考: ≥3000条 / ≥10人 / 常用指令各≥100条")
    print(f"  每指令覆盖 (前15):")
    for cmd, n in per_cmd.most_common(15):
        print(f"    {cmd:16s} {n:5d} {'✓' if n >= 100 else ''}")


def main():
    args = sys.argv[1:]
    if not args:
        if os.path.exists(MANIFEST):
            report()
        else:
            print(__doc__)
        return
    zips = []
    for a in args:
        if os.path.isdir(a):
            zips += glob.glob(os.path.join(a, "*.zip"))
        elif a.endswith(".zip"):
            zips.append(a)
    if not zips:
        print("没找到 zip。")
        return
    os.makedirs(CORPUS, exist_ok=True)
    seen = _load_seen()
    with open(MANIFEST, "a", encoding="utf-8") as mf:
        for zp in zips:
            added, skipped = ingest_zip(zp, seen, mf)
            print(f"  {os.path.basename(zp)}: 收入 {added} 条, 去重跳过 {skipped}")
    report()


if __name__ == "__main__":
    main()
