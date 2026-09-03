"""麦克风采集 —— push-to-talk 录音 + 持续监听 (VAD 自动断句)。

设备选择: settings.yaml 的 audio.device 存设备**名字**(字符串), 启动时
解析成索引 (名字比索引稳定, 插拔设备/重启后索引会变)。null = 系统默认。

采样率兜底: 很多 WASAPI 设备不支持 16kHz 直开, 失败时自动改用设备
原生采样率打开, 采完再软件重采样到 16kHz 喂给 Whisper。
"""
import collections
import math
import queue

import numpy as np
import sounddevice as sd

from i18n import t

TARGET_SR = 16000


def resolve_input_device(name):
    """把设备名解析成 sounddevice 的设备索引。

    None/空 = 系统默认 (返回 None)。优先 WASAPI 的同名设备 (名字全、延迟低)。
    找不到时抛 ValueError, 提示用户重新选设备。
    """
    if name in (None, "", "default"):
        return None
    if isinstance(name, int):
        return name  # 兼容旧配置里存的索引
    devs = sd.query_devices()
    apis = sd.query_hostapis()
    exact, fuzzy = [], []
    for i, d in enumerate(devs):
        if d["max_input_channels"] <= 0:
            continue
        api = apis[d["hostapi"]]["name"]
        if d["name"] == name:
            exact.append((i, api))
        elif name in d["name"] or d["name"] in name:
            fuzzy.append((i, api))
    for pool in (exact, fuzzy):
        wasapi = [i for i, api in pool if "WASAPI" in api]
        if wasapi:
            return wasapi[0]
        if pool:
            return pool[0][0]
    raise ValueError(
        t("找不到输入设备「{name}」, 请打开音频输入设置重新选择。").format(name=name)
    )


def input_device_label(device_index):
    """给日志用: 设备索引 -> 可读名字。"""
    if device_index is None:
        idx = sd.default.device[0]
        return f"系统默认 ({sd.query_devices(idx)['name']})"
    return sd.query_devices(device_index)["name"]


def _sibling_devices(device_index):
    """同名(同物理)设备在各 hostapi 上的候选索引。

    优先 WASAPI, 其次 MME / DirectSound —— 后两者走系统混音器,
    自带格式转换, 经常能在 WASAPI 打不开时救场。
    MME 的设备名可能被截断到 31 字符, 所以用前缀匹配。
    """
    if device_index is None:
        return [None]
    name = sd.query_devices(device_index)["name"]
    apis = sd.query_hostapis()
    order = {"Windows WASAPI": 0, "MME": 1, "Windows DirectSound": 2}
    found = []
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] <= 0:
            continue
        api = apis[d["hostapi"]]["name"]
        if api not in order:
            continue
        n = d["name"]
        same = n == name or (len(n) >= 10 and (name.startswith(n) or n.startswith(name)))
        if same:
            found.append((order[api], i))
    return [i for _, i in sorted(found)] or [device_index]


def open_input_stream(device_index, blocksize_sec=None, callback=None):
    """打开**并启动**输入流, 返回 (已启动的 stream, 实际采样率)。

    WASAPI 有个坑: 不支持的格式在创建时不报错, start() 时才抛
    AUDCLNT_E_UNSUPPORTED_FORMAT, 所以必须 start 成功才算成功。
    打不开就换参数、换同名设备的其他通道 (MME/DirectSound), 逐一尝试。
    """
    errors = []
    for dev in _sibling_devices(device_index):
        info = sd.query_devices(
            dev if dev is not None else sd.default.device[0]
        )
        hostapi = sd.query_hostapis(info["hostapi"])["name"]
        native_sr = int(info["default_samplerate"])

        attempts = []
        if "WASAPI" in hostapi:
            ws = sd.WasapiSettings(auto_convert=True)
            attempts += [(TARGET_SR, ws), (native_sr, ws)]
        for sr in (TARGET_SR, native_sr, 48000, 44100):
            if (sr, None) not in attempts:
                attempts.append((sr, None))

        for sr, extra in attempts:
            blocksize = int(sr * blocksize_sec) if blocksize_sec else 0
            try:
                stream = sd.InputStream(
                    samplerate=sr, channels=1, dtype="float32",
                    device=dev, blocksize=blocksize,
                    callback=callback, extra_settings=extra,
                )
                try:
                    stream.start()   # 真正的坑在这一步, 必须验证
                except Exception:
                    stream.close()
                    raise
                print(f"[音频] 已打开: {info['name']} ({hostapi}, {sr}Hz)")
                return stream, sr
            except Exception as e:
                msg = str(e).splitlines()[0]
                errors.append(f"{hostapi}/{sr}Hz{'+ac' if extra else ''}: {msg}")

    name = sd.query_devices(
        device_index if device_index is not None else sd.default.device[0]
    )["name"]
    raise RuntimeError(
        t("输入设备「{name}」的所有通道都无法打开。\n"
          "最可能的原因: 它被其他软件独占 (如 Voicemeeter 把它当硬件输入)。\n"
          "解决: 打开「语音指挥·音频设置」, 改选一路能跳绿条的设备 "
          "(比如 Voicemeeter Out B1 或 NVIDIA Broadcast)。\n"
          "详细尝试记录: {errors}").format(name=name, errors=" | ".join(errors))
    )


def resample_to_target(audio, src_sr):
    """线性插值重采样到 16kHz (语音识别足够)。"""
    if src_sr == TARGET_SR or audio.size == 0:
        return audio.astype(np.float32)
    n_out = int(round(audio.size * TARGET_SR / src_sr))
    x_out = np.linspace(0.0, audio.size - 1, n_out)
    return np.interp(x_out, np.arange(audio.size), audio).astype(np.float32)


class Recorder:
    def __init__(self, cfg: dict):
        a = cfg["audio"]
        self.samplerate = a.get("samplerate", TARGET_SR)
        self.device = resolve_input_device(a.get("device"))
        self._frames = []
        self._stream = None
        self._stream_sr = TARGET_SR

    def _callback(self, indata, frames, time_info, status):
        self._frames.append(indata.copy())

    def start(self):
        """开始录音 (热键按下时调用)。open_input_stream 返回的流已启动。"""
        self._frames = []
        self._stream, self._stream_sr = open_input_stream(
            self.device, callback=self._callback
        )

    def stop(self):
        """停止录音并返回采集到的音频 (热键松开时调用), 已重采样到 16kHz。"""
        if self._stream is None:
            return np.zeros(0, dtype=np.float32)
        self._stream.stop()
        self._stream.close()
        self._stream = None
        if not self._frames:
            return np.zeros(0, dtype=np.float32)
        audio = np.concatenate(self._frames, axis=0).flatten()
        return resample_to_target(audio.astype(np.float32), self._stream_sr)


class ContinuousListener:
    """持续监听麦克风, 用能量 VAD 自动把语音切成一句一句。

    用法:
        listener = ContinuousListener(cfg)
        for audio in listener.segments():   # 每检测到一句就 yield 一段音频
            ...
        # 别的线程调 listener.stop() 可结束循环
    """

    def __init__(self, cfg: dict):
        a = cfg["audio"]
        v = cfg.get("vad", {})
        self.sr = a.get("samplerate", TARGET_SR)   # 目标(喂 Whisper)采样率
        self.device = resolve_input_device(a.get("device"))
        self.frame_ms = 30
        self.frame_len = int(self.sr * self.frame_ms / 1000)
        # 开始说话/结束说话的能量阈值 (RMS)
        self.start_rms = v.get("start_rms", 0.02)
        self.end_rms = v.get("end_rms", 0.012)
        # 一句话至少多长才算有效 (秒)
        self.min_speech = v.get("min_speech_sec", 0.3)
        # 说完后静音多久判定一句结束 (秒)
        self.end_silence = v.get("end_silence_sec", 0.6)
        # 单句最长 (秒), 防跑飞
        self.max_speech = v.get("max_speech_sec", 8.0)
        # 句首预收音, 避免吃掉开头的字 (秒)
        self.preroll = v.get("preroll_sec", 0.25)
        self._q = queue.Queue()
        self.running = False
        self._frame_sec = self.frame_ms / 1000.0
        self._reset()

    def _reset(self):
        self._ring = collections.deque(
            maxlen=max(1, int(self.preroll / self._frame_sec))
        )
        self._voiced = []
        self._in_speech = False
        self._silence_run = 0.0
        self._speech_len = 0.0
        self._loud_len = 0.0   # 真正有声(过 end_rms)的累计时长, 用于 min_speech

    def feed(self, frame):
        """喂入一帧音频, 检测到完整一句时返回该段音频, 否则返回 None。

        与麦克风解耦, 方便单测 VAD 状态机。
        """
        rms = math.sqrt(float(np.mean(frame ** 2)) + 1e-12)
        if not self._in_speech:
            self._ring.append(frame)
            if rms >= self.start_rms:
                self._in_speech = True
                self._voiced = list(self._ring)           # 带上预收音
                self._speech_len = len(self._voiced) * self._frame_sec
                self._silence_run = 0.0
                self._loud_len = self._frame_sec          # 触发帧本身算有声
            return None

        self._voiced.append(frame)
        self._speech_len += self._frame_sec
        if rms < self.end_rms:
            self._silence_run += self._frame_sec
        else:
            self._silence_run = 0.0
            self._loud_len += self._frame_sec
        if self._silence_run >= self.end_silence or self._speech_len >= self.max_speech:
            loud = self._loud_len
            audio = np.concatenate(self._voiced).astype(np.float32)
            self._reset()
            return audio if loud >= self.min_speech else None
        return None

    def _callback(self, indata, frames, time_info, status):
        self._q.put(indata.copy())

    def stop(self):
        self.running = False

    def segments(self):
        self.running = True
        self._reset()
        # open_input_stream 返回的流已启动, 不能再用 with (会二次 start)
        stream, stream_sr = open_input_stream(
            self.device, blocksize_sec=self.frame_ms / 1000.0,
            callback=self._callback,
        )
        try:
            while self.running:
                try:
                    block = self._q.get(timeout=0.1)
                except queue.Empty:
                    continue
                seg = self.feed(block.flatten())
                if seg is not None:
                    yield resample_to_target(seg, stream_sr)
        finally:
            stream.stop()
            stream.close()


def list_devices():
    print(sd.query_devices())
