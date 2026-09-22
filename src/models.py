"""模型下载与就绪状态 —— 让用户看到"要下多大、下到哪了、好没好"。

就绪 = 手动目录(<用户数据>/models/<模型名>/)或 HF 缓存里有 model.bin。
下载 = 自己的 HTTP 下载器: 各源并行测速择优 + 断点续传 + 卡住换源 + sha256 校验,
落到手动目录(详见下方"下载"一节的教训)。
"""
import glob
import os
import threading
import time

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
# HF 协议的下载源: 用户自设 HF_ENDPOINT > huggingface.co 官方 > hf-mirror.com(国内可用,
# 海外会 308 回 hf.co)。教训(2026-09-09): 曾把 HF_ENDPOINT 全局写死 hf-mirror, 海外全挂;
# 不再全局改 HF_ENDPOINT(会连累 faster-whisper 自己的缓存解析)。
def endpoints():
    seen, out = set(), []
    for e in (os.environ.get("HF_ENDPOINT"), "https://huggingface.co", "https://hf-mirror.com"):
        e = (e or "").strip().rstrip("/")
        if e and e not in seen:
            seen.add(e)
            out.append(e)
    return out


class ModelDownloadError(RuntimeError):
    """所有下载源都失败。message 已是给用户看的一句话。"""

# 语言中立写法 (≈), 中英 UI 都能直接嵌用
_SIZE = {
    "tiny": "≈ 75 MB", "base": "≈ 145 MB", "small": "≈ 480 MB",
    "medium": "≈ 1.5 GB", "large-v3": "≈ 3 GB", "large-v3-turbo": "≈ 1.6 GB",
}
def _hub_cache():
    """HF 缓存根: 尊重 HF_HOME / HF_HUB_CACHE(用户可能挪到别的盘), 否则默认位置。"""
    try:
        from huggingface_hub.constants import HF_HUB_CACHE
        return HF_HUB_CACHE
    except Exception:
        return os.path.expanduser("~/.cache/huggingface/hub")


_CACHE = _hub_cache()


def model_repo(model):
    try:
        from faster_whisper.utils import _MODELS
        return _MODELS.get(model, model)
    except Exception:
        return model


def _cache_dir(model):
    return os.path.join(_CACHE, "models--" + model_repo(model).replace("/", "--"))


def manual_dir(model):
    """手动放模型 / ModelScope 下载落地的目录: <用户数据>\\models\\<模型名>\\。
    stt.bundled_model_path 最先看这里, 所以它和 HF 缓存一样算"就绪"。"""
    from paths import user_data_dir
    return os.path.join(user_data_dir(), "models", model)


def is_ready(model):
    """模型是否已完整下载 (手动目录或 HF 缓存里有像样的 model.bin)。"""
    if model in (None, "", "auto"):
        return True
    try:
        if os.path.getsize(os.path.join(manual_dir(model), "model.bin")) > 20_000_000:
            return True
    except Exception:
        pass
    d = _cache_dir(model)
    if not os.path.isdir(d):
        return False
    bins = glob.glob(os.path.join(d, "snapshots", "*", "model.bin"))
    bins += glob.glob(os.path.join(d, "blobs", "*"))
    return any(os.path.getsize(b) > 20_000_000 for b in bins)


def size_hint(model):
    return _SIZE.get(model, "?")


_UA = {"User-Agent": "BannerlordVoice/model-download"}
# 魔搭(阿里): 六个 faster-whisper 模型同名同文件(2026-09-09 核实), 国内直连。
MODELSCOPE = "https://www.modelscope.cn"


# ---------- 下载: 自己的 HTTP 下载器, 各源并行测速后择优 ----------
# 教训(2026-09-22, 国内用户持续报"下不了", 用 Globalping 大陆探针查实):
#   * huggingface.co 在大陆 TCP 都连不上(15s 超时) —— 预期之中。
#   * hf-mirror.com 没关站, 是按地区 308: 海外跳回 hf.co, 国内正常服务。但它只镜像元数据,
#     大文件 model.bin 302 到 HF 自家美国 xet CDN(cas-bridge.xethub.hf.co/xet-bridge-us)。
#     该 CDN 在国内"通但极慢/会卡死", 旧实现 4s HEAD 探通 = 可达 -> 交给 huggingface_hub
#     去下, 卡住不抛错 -> 永远轮不到魔搭, 用户看到进度条不动。
#   * 魔搭对 HEAD 回 404(GET 正常), 探活不能用 HEAD。
# 所以: 不再用 snapshot_download/xet。每个源先列文件, 再拿 model.bin 真实下几 MB 测速
# (并行, 几秒), 按实测速度排序; 下载用 Range 断点续传, 卡住(读超时)或太慢自动换下一个源
# 续传(各源同一文件 sha256 相同, 已核实), 完成后校验 sha256。落地 manual_dir(model)。
PROBE_SECS = 3.0            # 每源测速时长
PROBE_BYTES = 8 << 20       # 每源测速最多下多少
LIST_TIMEOUT = 8            # 列文件接口超时
READ_TIMEOUT = 20           # 下载中一次读卡住这么久 = 该源卡死, 换源
SLOW_WINDOW = 30.0          # 这段时间内均速低于 SLOW_BPS 且还有别的源 -> 换源
SLOW_BPS = 64 << 10
_SKIP = (".gitattributes", "README.md")


def _sources():
    """[(base, kind)]: kind=hf(HF 协议: 用户 HF_ENDPOINT / hf.co / hf-mirror) 或 ms(魔搭)。"""
    return [(e, "hf") for e in endpoints()] + [(MODELSCOPE, "ms")]


def _get(url, timeout, headers=None):
    import urllib.request
    h = dict(_UA)
    h.update(headers or {})
    return urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout)


def _list_files(base, kind, repo):
    """[(path, size, sha256|None)], 必含 model.bin。"""
    import json
    if kind == "ms":
        u = f"{base}/api/v1/models/{repo}/repo/files?Revision=master&Recursive=true"
        with _get(u, LIST_TIMEOUT) as r:
            d = json.load(r)
        files = [(f["Path"], int(f["Size"]), f.get("Sha256") or None)
                 for f in d["Data"]["Files"] if f.get("Type") == "blob"]
    else:
        with _get(f"{base}/api/models/{repo}/tree/main", LIST_TIMEOUT) as r:
            d = json.load(r)
        files = [(f["path"], int(f["size"]), (f.get("lfs") or {}).get("oid"))
                 for f in d if f.get("type") == "file"]
    files = [f for f in files if f[0] not in _SKIP]
    if not any(p == "model.bin" for p, _, _ in files):
        raise RuntimeError("no model.bin")
    return files


def _file_url(base, kind, repo, path):
    if kind == "ms":
        return f"{base}/models/{repo}/resolve/master/{path}"
    return f"{base}/{repo}/resolve/main/{path}"


def _probe(base, kind, repo):
    """列文件 + 拿 model.bin 真下几 MB -> (files, 字节/秒)。失败抛异常。"""
    files = _list_files(base, kind, repo)
    t0 = time.time()
    got = 0
    try:
        with _get(_file_url(base, kind, repo, "model.bin"), PROBE_SECS + 2,
                  {"Range": f"bytes=0-{PROBE_BYTES - 1}"}) as r:
            while got < PROBE_BYTES and time.time() - t0 < PROBE_SECS:
                c = r.read1(256 << 10)
                if not c:
                    break
                got += len(c)
    except Exception:
        if not got:                      # 下了一点就卡住 = 慢源, 按实测速度排到后面
            raise
    return files, got / max(time.time() - t0, 0.05)


def _rank_sources(repo):
    """并行测速所有源 -> ([(base, kind, bps)] 快的在前, files, errors)。"""
    srcs = _sources()
    res = [None] * len(srcs)

    def run(i, base, kind):
        try:
            res[i] = _probe(base, kind, repo)
        except Exception as e:
            res[i] = e

    ths = [threading.Thread(target=run, args=(i, b, k), daemon=True)
           for i, (b, k) in enumerate(srcs)]
    for t in ths:
        t.start()
    deadline = time.time() + LIST_TIMEOUT + PROBE_SECS + 6
    for t in ths:
        t.join(max(0.0, deadline - time.time()))
    ranked, errors, files = [], [], None
    for (base, kind), r in zip(srcs, list(res)):
        if isinstance(r, tuple) and r[1] > 0:
            ranked.append((base, kind, r[1], r[0]))
        else:
            errors.append(f"{base}: {type(r).__name__ if r is not None else 'timeout'}")
    ranked.sort(key=lambda x: -x[2])
    if ranked:
        files = ranked[0][3]              # 文件清单以最快源为准(各源同名同内容)
    print("[模型] 下载源测速: " + ", ".join(
        f"{b.split('//')[-1]} {bps / 1048576:.1f}MB/s" for b, _, bps, _ in ranked)
          + ("; 不通: " + ", ".join(errors) if errors else ""))
    return [(b, k, bps) for b, k, bps, _ in ranked], files, errors


class _Slow(Exception):
    pass


def _fetch_resume(url, part, size, on_progress, can_switch):
    """把 url 续传进 part(已有字节从断点接着下), 直到 size 字节。
    读卡住 READ_TIMEOUT 抛超时; 可换源时均速太慢抛 _Slow。"""
    have = os.path.getsize(part) if os.path.exists(part) else 0
    if have > size:
        os.remove(part)
        have = 0
    if have == size:
        return
    hdr = {"Range": f"bytes={have}-"} if have else {}
    with _get(url, READ_TIMEOUT, hdr) as r:
        if have and getattr(r, "status", 200) != 206:
            have = 0                     # 源不支持续传: 从头来
        win_t, win_b = time.time(), 0
        with open(part, "ab" if have else "wb") as f:
            while have < size:
                c = r.read1(1 << 20)
                if not c:
                    break
                f.write(c)
                have += len(c)
                win_b += len(c)
                on_progress(have)
                el = time.time() - win_t
                if el >= SLOW_WINDOW:
                    if can_switch and win_b / el < SLOW_BPS:
                        raise _Slow(f"{win_b / el / 1024:.0f}KB/s")
                    win_t, win_b = time.time(), 0
    if have < size:
        raise ConnectionError(f"short read {have}/{size}")


def _sha256(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(4 << 20), b""):
            h.update(c)
    return h.hexdigest()


def download(model, progress_cb=None):
    """下载模型到 manual_dir(model)。progress_cb(done_bytes, total_bytes); total=0 = 测速中。
    成功返回 True; 所有源都不行抛 ModelDownloadError(消息可直接给用户看)。"""
    repo = model_repo(model)
    if progress_cb:
        progress_cb(0, 0)
    ranked, files, errors = _rank_sources(repo)
    if not ranked:
        raise ModelDownloadError(user_message(model, errors))
    dst = manual_dir(model)
    os.makedirs(dst, exist_ok=True)
    total = sum(s for _, s, _ in files)
    done = 0
    # model.bin 放最后: 它在 = 就绪(is_ready/stt 都认它), 不能在别的文件没齐时先出现
    for path, size, sha in sorted(files, key=lambda f: f[0] == "model.bin"):
        out = os.path.join(dst, path)
        if os.path.isfile(out) and os.path.getsize(out) == size:
            done += size
            continue
        os.makedirs(os.path.dirname(out), exist_ok=True)
        part = out + ".part"
        tries, last = 0, None
        while True:
            if tries >= 3 * len(ranked):
                errors.append(f"{last}: {path}")
                raise ModelDownloadError(user_message(model, errors))
            base, kind, _ = ranked[0]
            tries += 1
            try:
                _fetch_resume(_file_url(base, kind, repo, path), part, size,
                              lambda have: progress_cb and progress_cb(done + have, total),
                              can_switch=len(ranked) > 1)
                break
            except Exception as e:
                last = f"{base}: {type(e).__name__}"
                print(f"[模型] {path} 从 {base} 下载中断({type(e).__name__}: "
                      f"{str(e)[:120]}), 换源续传")
                ranked.append(ranked.pop(0))      # 当前源排到最后, 下一个接着续传
        if sha and len(sha) == 64 and _sha256(part) != sha:
            os.remove(part)
            errors.append(f"{ranked[0][0]}: {path} sha256 mismatch")
            raise ModelDownloadError(user_message(model, errors))
        os.replace(part, out)
        done += size
    if progress_cb:
        progress_cb(total, total)
    print(f"[模型] {model} 已下到 {dst}")
    return True


def user_message(model, errors):
    """全部下载源失败时给用户看的一句话(双语; 只说他能做的事: 代理 / 手动放模型)。"""
    try:
        from i18n import t
    except Exception:          # 纯逻辑测试环境
        def t(s):
            return s
    tried = ", ".join(e.split("//")[-1].split(":")[0] for e in errors) or "-"
    return t("连不上模型下载源 (试过 {tried})。国内需要代理; 或把模型文件夹手动放到 "
             "{path} (含 model.bin)").format(
        tried=tried, path=f"%LOCALAPPDATA%\\BannerlordVoice\\models\\{model}\\")
