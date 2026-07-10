# -*- coding: utf-8 -*-
"""语音数据共建 —— 自愿留存指令语音片段, 为微调专用小模型攒语料。

隐私原则 (对用户的承诺, 改动前先想清楚):
  1. 默认关。启动器里自愿勾选, 首次开启弹完整说明。
  2. 只保存"被识别为指令并执行"的短片段 + 识别文本标注;
     聊天/未匹配的话默认不保存 (keep_misses 显式打开才存, 且导出时单列)。
  3. 数据只在本机 %LOCALAPPDATA%\\BannerlordVoice\\donation\\,
     用户主动点"导出数据包"才会产生离开本机的文件。
  4. 随时可关; 打开文件夹删掉即可清空。
  5. 数据包只含: wav 片段 / 识别标注 / 软件版本 / 匿名机器指纹(16位哈希,
     不含任何个人信息) —— 指纹只用于归集时区分说话人。

作者侧归集: tools/ingest_donations.py 把收到的 zip 并入语料库并出统计。
"""
import json
import os
import time
import zipfile

APP_DIRNAME = "BannerlordVoice"
MAX_MB_DEFAULT = 500


def donation_dir():
    d = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                     APP_DIRNAME, "donation")
    os.makedirs(d, exist_ok=True)
    return d


def _manifest():
    return os.path.join(donation_dir(), "manifest.jsonl")


def _total_mb():
    total = 0
    d = donation_dir()
    for fn in os.listdir(d):
        try:
            total += os.path.getsize(os.path.join(d, fn))
        except OSError:
            pass
    return total / 1048576


class Donation:
    """采集器: enabled=False 时所有调用都是零开销空操作。"""

    def __init__(self, settings):
        cfg = settings.get("data_donation") or {}
        self.enabled = bool(cfg.get("enabled", False))
        self.keep_misses = bool(cfg.get("keep_misses", False))
        self.max_mb = cfg.get("max_mb", MAX_MB_DEFAULT)
        self.lang = (settings.get("stt") or {}).get("language", "zh")
        self._full_warned = False

    def save(self, audio, sr, result, group, order, text, engine="", target=""):
        """存一条指令片段。绝不抛异常影响主流程。"""
        if not self.enabled:
            return
        if result != "ok" and not self.keep_misses:
            return
        try:
            if _total_mb() >= self.max_mb:
                if not self._full_warned:
                    self._full_warned = True
                    print(f"[共建] 本机留存已达 {self.max_mb}MB 上限, 暂停保存 "
                          f"(导出并清空后恢复)。")
                return
            import soundfile as sf
            ts = time.strftime("%Y%m%d-%H%M%S")
            name = f"{ts}-{int(time.time() * 1000) % 1000:03d}.wav"
            sf.write(os.path.join(donation_dir(), name), audio, sr)
            from version import APP_VERSION
            from machine_id import machine_id
            rec = {"file": name, "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                   "lang": self.lang, "result": result,
                   "group": group or "", "order": order or "",
                   "target": target or "",
                   "text": (text or "")[:120], "engine": engine,
                   "app": APP_VERSION, "speaker": machine_id()}
            with open(_manifest(), "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception:
            pass


def stats():
    """(条数, 总MB) —— 启动器展示用。"""
    n = 0
    try:
        with open(_manifest(), encoding="utf-8") as f:
            n = sum(1 for line in f if line.strip())
    except Exception:
        pass
    return n, round(_total_mb(), 1)


def export_zip():
    """把本机留存打成一个 zip (含清单), 返回 zip 路径; 没有数据返回 None。

    zip 放在 donation 目录旁边, 文件名带匿名指纹前8位 —— 用户把它发给作者
    (群/网盘/邮箱都行), 这是数据离开本机的唯一途径。
    """
    from machine_id import machine_id
    from version import APP_VERSION
    d = donation_dir()
    wavs = [f for f in os.listdir(d) if f.endswith(".wav")]
    if not wavs or not os.path.exists(_manifest()):
        return None
    out = os.path.join(
        os.path.dirname(d),
        f"语音数据包-{machine_id()[:8]}-{time.strftime('%Y%m%d')}.zip")
    meta = {"speaker": machine_id(), "app": APP_VERSION,
            "exported": time.strftime("%Y-%m-%d %H:%M:%S"), "count": len(wavs)}
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("meta.json", json.dumps(meta, ensure_ascii=False, indent=2))
        z.write(_manifest(), "manifest.jsonl")
        for f in wavs:
            z.write(os.path.join(d, f), f"wav/{f}")
        # 校准录音也一并带上 (同样是本人朗读的指令语料)
        cal = os.path.join(os.path.dirname(d), "calibration")
        if os.path.isdir(cal):
            for f in os.listdir(cal):
                if f.endswith(".wav"):
                    z.write(os.path.join(cal, f), f"calibration/{f}")
    return out


CONSENT_TEXT = (
    "参与「语音数据共建」意味着:\n\n"
    "· 只保存「被识别为指令并执行」的那 1~2 秒语音片段和识别文本\n"
    "  (聊天、闲话、未匹配的内容一律不保存)\n"
    "· 数据只存在你自己电脑上 (%LOCALAPPDATA%\\BannerlordVoice\\donation)\n"
    "· 只有你自己点「导出数据包」并把它发给作者, 数据才会离开你的电脑\n"
    "· 数据包只含语音片段、指令标注、软件版本和一个匿名机器编号,\n"
    "  不含你的任何个人信息\n"
    "· 用途: 训练/微调更小更快的指令识别模型, 让所有玩家受益\n"
    "· 随时可以取消勾选停止保存; 删掉那个文件夹即可清空\n\n"
    "确认参与吗?"
)
