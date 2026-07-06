"""骑砍语音指挥 —— 主程序。

两种模式:
  continuous   一直监听, VAD 自动断句, 匹配到指令就发 (像 VoiceAttack)
  push_to_talk 按住热键说话, 松开识别

数据流: 麦克风 -> Whisper识别 -> (可选口令前缀) -> 模糊匹配 -> 模拟按键
"""
import os
import sys
import threading
import time

# Windows 控制台默认 GBK, 强制 UTF-8 避免中文/符号打印崩溃
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

import keyboard
import numpy as np
import yaml
from rapidfuzz import fuzz

from audio import (ContinuousListener, Recorder, input_device_label,
                   resolve_input_device)
from executor import Executor
from matcher import Matcher
from overlay import Overlay
from stt import Transcriber

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def boost_priority():
    """提高进程优先级并关闭 Windows 电源节流。

    游戏在前台时, 系统会对"后台"进程降权(游戏模式/EcoQoS),
    否则识别线程可能被饿到几乎不跑。
    """
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        # 64 位下句柄必须按 HANDLE 传, 否则被截断成 32 位而静默失败
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        kernel32.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel32.GetPriorityClass.argtypes = [wintypes.HANDLE]
        kernel32.GetPriorityClass.restype = wintypes.DWORD

        h = kernel32.GetCurrentProcess()
        HIGH_PRIORITY_CLASS = 0x00000080
        kernel32.SetPriorityClass(h, HIGH_PRIORITY_CLASS)
        got = kernel32.GetPriorityClass(h)
        if got == HIGH_PRIORITY_CLASS:
            print("[系统] 进程优先级已提升 (HIGH)。")
        else:
            print(f"[系统] ⚠ 优先级提升未生效 (当前 {hex(got)}), 不影响使用。")

        class _ThrottleState(ctypes.Structure):
            _fields_ = [
                ("Version", ctypes.c_ulong),
                ("ControlMask", ctypes.c_ulong),
                ("StateMask", ctypes.c_ulong),
            ]

        kernel32.SetProcessInformation.argtypes = [
            wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
        ]
        POWER_THROTTLING_EXECUTION_SPEED = 0x1
        # StateMask=0 => 明确"不要节流"
        state = _ThrottleState(1, POWER_THROTTLING_EXECUTION_SPEED, 0)
        ProcessPowerThrottling = 4
        ok = kernel32.SetProcessInformation(
            h, ProcessPowerThrottling, ctypes.byref(state), ctypes.sizeof(state)
        )
        print(f"[系统] 电源节流: {'已关闭' if ok else '关闭失败(不影响使用)'}。")
    except Exception as e:
        print(f"[系统] ⚠ 优先级提升失败 (不影响使用): {e}")


def boost_thread_priority():
    """把当前线程(识别工作线程)提到 HIGHEST, 在进程优先级类内再抬一档。"""
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        kernel32.GetCurrentThread.restype = wintypes.HANDLE
        kernel32.SetThreadPriority.argtypes = [wintypes.HANDLE, ctypes.c_int]
        THREAD_PRIORITY_HIGHEST = 2
        ok = kernel32.SetThreadPriority(
            kernel32.GetCurrentThread(), THREAD_PRIORITY_HIGHEST
        )
        print(f"[系统] 识别线程优先级: {'HIGHEST' if ok else '提升失败(不影响使用)'}。")
    except Exception as e:
        print(f"[系统] ⚠ 线程优先级提升失败 (不影响使用): {e}")


def load_cfg():
    from paths import config_path
    with open(config_path("settings.yaml"), encoding="utf-8") as f:
        settings = yaml.safe_load(f)
    with open(config_path("commands.yaml"), encoding="utf-8") as f:
        commands = yaml.safe_load(f)
    return settings, commands


def describe(parsed, commands):
    """生成给浮层/控制台看的中文描述。"""
    parts = []
    if parsed.get("group"):
        g = parsed["group"]["name"]
        parts.append(commands["groups"][g]["aliases"][0])
    if parsed.get("order"):
        o = parsed["order"]["name"]
        parts.append(commands["orders"][o]["aliases"][0])
    return " · ".join(parts) if parts else "?"


class App:
    def __init__(self, settings, commands, overlay=None):
        c = settings["control"]
        self.settings = settings
        self.commands = commands
        self.overlay = overlay
        self.mode = c.get("mode", "continuous")
        self.ptt = c.get("push_to_talk_key", "caps lock")
        self.reload_key = c.get("reload_key") or ""
        self.prefixes = c.get("command_prefix") or []
        self.dry_run = "--dry-run" in sys.argv
        self.samplerate = settings["audio"]["samplerate"]
        self.silence_rms = settings["audio"].get("silence_rms", 0.006)
        self.slow_warn_sec = settings["stt"].get("slow_warn_sec", 3.0)
        self.matcher = Matcher(
            commands, c["match_threshold"], c.get("chat_filter", True)
        )
        if self.dry_run:
            print("[模式] dry-run: 只打印按键, 不真的发送。")
        self.executor = Executor(settings, commands, dry_run=self.dry_run)
        self.listener = None
        try:
            dev = resolve_input_device(settings["audio"].get("device"))
            print(f"[音频] 输入设备: {input_device_label(dev)}")
        except ValueError as e:
            print(f"[音频] ⚠ {e}")
        self.transcriber = Transcriber(settings)  # 加载模型 (慢)
        self.running = True

    def _set(self, status, detail="", color="#FFFFFF"):
        print(f"  {status}  {detail}")
        if self.overlay:
            self.overlay.push(status, detail, color)

    def _idle(self, detail=""):
        if self.mode == "continuous":
            self._set("👂 监听中…", detail or "说出指令即可", "#7Fd1ff")
        else:
            self._set("待命中…", detail or f"按住 [{self.ptt}] 说话", "#7Fd1ff")

    def reload_config(self):
        """热重载词典/阈值到运行中的引擎 (Whisper 模型不动)。热键回调。"""
        try:
            settings, commands = load_cfg()
        except Exception as e:
            self._set("⚠ 词典重载失败", f"YAML 有错: {e}", "#ff8a8a")
            return
        c = settings["control"]
        self.commands = commands
        self.matcher = Matcher(
            commands, c["match_threshold"], c.get("chat_filter", True)
        )
        self.executor = Executor(settings, commands, dry_run=self.dry_run)
        self.prefixes = c.get("command_prefix") or []
        self.silence_rms = settings["audio"].get("silence_rms", self.silence_rms)
        n = sum(len(d.get("aliases", []))
                for sec in ("groups", "orders")
                for d in commands.get(sec, {}).values())
        print(f"[重载] 词典已刷新: {n} 条别名, 立即生效。")
        self._set("🔄 词典已重载", f"{n} 条说法已生效", "#7dff9b")

    def _register_reload_hotkey(self):
        if not self.reload_key:
            return
        try:
            keyboard.add_hotkey(self.reload_key, self.reload_config)
            print(f"[重载] 按 [{self.reload_key.upper()}] 可热重载词典 (改完不用重启)。")
        except Exception as e:
            print(f"[重载] ⚠ 热键 {self.reload_key} 注册失败: {e}")

    def _check_prefix(self, text):
        """口令前缀过滤。返回 (是否放行, 去掉前缀后的文本)。

        未配置前缀 => 全部放行。配置了 => 必须先说前缀才执行。
        """
        if not self.prefixes:
            return True, text
        for p in self.prefixes:
            if p in text:
                return True, text.replace(p, "", 1).strip()
            if fuzz.partial_ratio(p, text) >= 80:
                return True, text  # 模糊命中前缀, 文本整体交给匹配
        return False, text

    def _handle(self, audio):
        """处理一段语音: 识别 -> 前缀 -> 匹配 -> 执行。带分阶段耗时日志。"""
        t_seg = time.perf_counter()
        secs = audio.shape[0] / self.samplerate
        print(f"[{time.strftime('%H:%M:%S')}] 🎧 捕到语音 {secs:.1f}s")

        rms = float(np.sqrt(np.mean(audio ** 2)))
        if rms < self.silence_rms:
            self._idle("(没听到声音)")
            return

        self._set("识别中…", "", "#c9a0ff")
        t0 = time.perf_counter()
        text = self.transcriber.transcribe(audio)
        t_stt = time.perf_counter() - t0
        if t_stt > self.slow_warn_sec:
            print(f"    [⚠ 识别偏慢] {t_stt:.1f}s (音频 {secs:.1f}s) "
                  f"—— 多半是游戏在抢 GPU, 试试游戏内锁帧/关游戏模式")
        if not text:
            print(f"    [耗时] 识别 {t_stt:.2f}s (没听清)")
            self._idle("(没听清)")
            return

        armed, cleaned = self._check_prefix(text)
        if not armed:
            print(f"    [耗时] 识别 {t_stt:.2f}s (无口令前缀, 忽略)")
            self._idle(f"听到: {text}")
            return

        parsed = self.matcher.parse(cleaned)
        if not parsed:
            print(f"    [耗时] 识别 {t_stt:.2f}s (未匹配/聊天)")
            self._set("未匹配", f"听到: {text}", "#ff8a8a")
            time.sleep(0.6)
            self._idle()
            return

        desc = describe(parsed, self.commands)
        t0 = time.perf_counter()
        self.executor.execute(parsed)
        t_keys = time.perf_counter() - t0
        total = time.perf_counter() - t_seg
        print(f"    [耗时] 识别 {t_stt:.2f}s + 按键 {t_keys:.2f}s = 共 {total:.2f}s")
        self._set(f"✓ {desc}", f"听到: {text}", "#7dff9b")

    # ---------- 持续监听模式 ----------
    def loop_continuous(self):
        self._idle()
        tip = "(已开口令前缀)" if self.prefixes else ""
        print(f"\n>>> 持续监听已开启 {tip}, 说出指令即可。Ctrl+C 退出。\n")
        try:
            self.listener = ContinuousListener(self.settings)
            for audio in self.listener.segments():
                if not self.running:
                    break
                self._handle(audio)
                if self.running:
                    self._idle()
        except Exception as e:
            print(f"\n[错误] {e}\n")
            self._set("⚠ 麦克风打开失败", "请打开「音频设置」换一路设备", "#ff8a8a")

    # ---------- 按住说话模式 ----------
    def loop_ptt(self):
        self.recorder = Recorder(self.settings)
        self._idle()
        print(f"\n>>> 按住 [{self.ptt}] 说话, 松开识别。Ctrl+C 退出。\n")
        while self.running:
            if not keyboard.is_pressed(self.ptt):
                time.sleep(0.02)
                continue
            self._set("🎙 录音中…", "", "#ffd479")
            self.recorder.start()
            while keyboard.is_pressed(self.ptt) and self.running:
                time.sleep(0.02)
            audio = self.recorder.stop()
            if audio.shape[0] < self.samplerate * 0.2:
                self._idle("(太短)")
                continue
            self._handle(audio)
            if self.running:
                self._idle()

    def loop(self):
        boost_thread_priority()
        self._register_reload_hotkey()
        if self.mode == "continuous":
            self.loop_continuous()
        else:
            self.loop_ptt()

    def stop(self):
        self.running = False
        if self.listener:
            self.listener.stop()
        if self.reload_key:
            try:
                keyboard.remove_hotkey(self.reload_key)
            except Exception:
                pass


def main():
    from license import LICENSE
    from version import APP_NAME, APP_VERSION
    print(f"=== {APP_NAME} v{APP_VERSION} · {LICENSE.status_line()} ===")
    boost_priority()
    settings, commands = load_cfg()
    use_overlay = settings.get("overlay", {}).get("enabled", False)

    if use_overlay:
        overlay = Overlay(settings)
        app = App(settings, commands, overlay)
        worker = threading.Thread(target=app.loop, daemon=True)
        worker.start()
        try:
            overlay.run()  # 阻塞在主线程
        finally:
            app.stop()
    else:
        app = App(settings, commands)
        try:
            app.loop()
        except KeyboardInterrupt:
            app.stop()
            print("\n再见。")


if __name__ == "__main__":
    main()
