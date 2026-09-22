# -*- coding: utf-8 -*-
"""国内用户视角的模型下载体检 —— 定期跑, 别再等用户来报"下不了"。

两段:
  1. 大陆探针(Globalping 公共 API, 免费免注册, 探针在腾讯云/阿里云/联通等大陆机房):
     从中国发请求看各下载源的 列文件接口 / model.bin 跳到哪个 CDN / 那个 CDN 通不通。
     只能测"通不通 + 首包耗时", 测不了下载速度(探针只收前 10KB)。
  2. 本机真下载(走 models.download 的真实代码路径): 下 tiny(75MB) 到临时目录,
     a) 全部源正常   b) 模拟国内 —— HF 系源换成黑洞(接 TCP 不回话, 就是大陆连 hf.co 的样子)
     下完用 faster-whisper 真加载一次。临时目录用完删, 不碰用户数据目录。

用法: .venv\\Scripts\\python tools\\cn_check.py [--probe-only | --local-only]
结果: 追加一行到 dist/cn_check/history.csv; 有问题退出码 1(给定时任务判红)。
"""
import csv
import json
import os
import shutil
import socket
import sys
import tempfile
import time
import urllib.error
import urllib.request

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import models  # noqa: E402

GP = "https://api.globalping.io/v1/measurements"
REPO = "Systran/faster-whisper-tiny"
OUT = os.path.join(ROOT, "dist", "cn_check")

# (名字, host, path, 期望)  期望: ok=2xx; redirect=3xx 且记下跳去的 host
CHECKS = [
    ("modelscope 列文件", "www.modelscope.cn",
     f"/api/v1/models/{REPO}/repo/files?Revision=master&Recursive=true", "ok"),
    ("modelscope model.bin", "www.modelscope.cn",
     f"/models/{REPO}/resolve/master/model.bin", "redirect"),
    ("hf-mirror 列文件", "hf-mirror.com", f"/api/models/{REPO}/tree/main", "ok"),
    ("hf-mirror model.bin", "hf-mirror.com", f"/{REPO}/resolve/main/model.bin", "redirect"),
    ("huggingface.co", "huggingface.co", f"/api/models/{REPO}", "info"),
]
MUST_PASS = {"modelscope 列文件", "modelscope model.bin"}   # 国内用户的保底路径


def _gp(host, path, method="GET", n=5):
    q = path.split("?", 1)
    req = {"method": method, "path": q[0]}
    if len(q) > 1:
        req["query"] = q[1]
    body = {"type": "http", "target": host, "locations": [{"country": "CN", "limit": n}],
            "measurementOptions": {"protocol": "HTTPS", "request": req}}
    r = urllib.request.Request(GP, data=json.dumps(body).encode(), method="POST",
                               headers={"Content-Type": "application/json"})
    mid = json.load(urllib.request.urlopen(r, timeout=20))["id"]
    for _ in range(40):
        time.sleep(1.5)
        d = json.load(urllib.request.urlopen(f"{GP}/{mid}", timeout=20))
        if d["status"] != "in-progress":
            break
    out = []
    for x in d["results"]:
        res = x["result"]
        hdr = {k.lower(): v for k, v in (res.get("headers") or {}).items()}
        out.append({"city": x["probe"].get("city"), "net": x["probe"].get("network", ""),
                    "ok": res.get("status") == "finished", "code": res.get("statusCode"),
                    "ms": (res.get("timings") or {}).get("total"),
                    "loc": hdr.get("location", ""),
                    "err": "" if res.get("status") == "finished" else
                    (res.get("rawOutput") or "").splitlines()[0][:60] if res.get("rawOutput") else "?"})
    return out


def _host(url):
    return url.split("//")[-1].split("/")[0] if "//" in url else "(相对路径)"


def probe_cn():
    """-> (问题列表, 摘要dict)"""
    problems, summary, cdns = [], {}, set()
    for name, host, path, want in CHECKS:
        try:
            rs = _gp(host, path)
        except Exception as e:
            problems.append(f"Globalping 调用失败 {name}: {e}")
            continue
        good = [r for r in rs if r["ok"] and r["code"] and
                (200 <= r["code"] < 300 if want == "ok" else
                 300 <= r["code"] < 400 if want == "redirect" else True)]
        summary[name] = f"{len(good)}/{len(rs)}"
        med = sorted(r["ms"] for r in rs if r["ms"])[len(rs) // 2] if rs else None
        locs = {_host(r["loc"]) for r in rs if r["loc"]}
        if want == "redirect":
            cdns |= {(name, h) for h in locs if h != "(相对路径)"}
        print(f"  {name:22s} 通 {len(good)}/{len(rs)}  中位 {med}ms"
              + (f"  跳到 {', '.join(sorted(locs))}" if locs else "")
              + ("" if good else "  ✗ " + "; ".join(sorted({r['err'] or str(r['code']) for r in rs}))))
        if name in MUST_PASS and len(good) < max(1, len(rs) - 1):
            problems.append(f"{name}: 大陆探针只通 {len(good)}/{len(rs)}")
    for name, cdn in sorted(cdns):
        try:
            rs = _gp(cdn, "/", method="HEAD", n=3)
            reach = sum(1 for r in rs if r["ok"])
            print(f"  └ CDN {cdn:32s} 大陆 TCP/TLS 可达 {reach}/{len(rs)}"
                  + ("  (美国 HF CDN: 通 ≠ 快, 国内实际常卡)" if "hf.co" in cdn else ""))
            summary[f"cdn {cdn}"] = f"{reach}/{len(rs)}"
            if name in MUST_PASS and reach < len(rs):
                problems.append(f"魔搭 CDN {cdn} 大陆可达只有 {reach}/{len(rs)}")
        except Exception as e:
            problems.append(f"CDN 探测失败 {cdn}: {e}")
    return problems, summary


def _blackhole():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    s.listen(50)
    return f"http://127.0.0.1:{s.getsockname()[1]}", s


def local_download(cn_sim):
    """真实代码路径下 tiny 到临时目录并加载。-> (ok, 说明)"""
    tmp = tempfile.mkdtemp(prefix="bv_cncheck_")
    orig_dir, orig_src = models.manual_dir, models._sources
    models.manual_dir = lambda m: os.path.join(tmp, m)
    hole = None
    if cn_sim:
        hole_url, hole = _blackhole()
        models._sources = lambda: [(hole_url, "hf"), (hole_url + "/", "hf"),
                                   (models.MODELSCOPE, "ms")]
    t0 = time.time()
    try:
        models.download("tiny")
        dl = time.time() - t0
        from faster_whisper import WhisperModel
        WhisperModel(os.path.join(tmp, "tiny"), device="cpu", compute_type="int8")
        return True, f"{dl:.0f}s 下完并加载成功"
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:160]}"
    finally:
        models.manual_dir, models._sources = orig_dir, orig_src
        if hole:
            hole.close()
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    problems, row = [], {"time": time.strftime("%Y-%m-%d %H:%M")}
    if "--local-only" not in sys.argv:
        print("① 大陆探针 (Globalping, CN):")
        p, s = probe_cn()
        problems += p
        row["probe"] = json.dumps(s, ensure_ascii=False)
    if "--probe-only" not in sys.argv:
        for label, sim in (("② 本机真下载 (全部源)", False), ("③ 本机模拟国内 (HF 系=黑洞)", True)):
            ok, msg = local_download(sim)
            print(f"{label}: {'✓' if ok else '✗'} {msg}")
            row["cn_sim" if sim else "all_sources"] = ("ok " if ok else "FAIL ") + msg
            if not ok:
                problems.append(f"{label}: {msg}")
    row["problems"] = " | ".join(problems)
    os.makedirs(OUT, exist_ok=True)
    hist = os.path.join(OUT, "history.csv")
    new = not os.path.exists(hist)
    with open(hist, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["time", "probe", "all_sources", "cn_sim", "problems"])
        if new:
            w.writeheader()
        w.writerow(row)
    print("\n" + ("✗ 有问题:\n  - " + "\n  - ".join(problems) if problems else "✓ 国内下载链路正常"))
    print(f"  记录: {hist}")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
