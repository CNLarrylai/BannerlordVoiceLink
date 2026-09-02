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
import usage
from executor import Executor
from i18n import t
from matcher import Matcher
from modlink import ModLink
from overlay import Overlay
from retry import RetryMemory
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
    import dictionary
    from paths import config_path
    with open(config_path("settings.yaml"), encoding="utf-8") as f:
        settings = yaml.safe_load(f)
    # 基础词典 + 个人词典(校准学到的说法)合并
    commands = dictionary.load_commands()
    return settings, commands


def _disp(data, lang):
    """该指令/兵种在当前语言下的显示名 (第一个别名)。"""
    al = data.get("en", []) if lang == "en" else data.get("aliases", [])
    return al[0] if al else "?"


def describe(parsed, commands, lang="zh"):
    """生成给浮层/控制台看的描述。"""
    parts = []
    if parsed.get("group"):
        parts.append(_disp(commands["groups"][parsed["group"]["name"]], lang))
    if parsed.get("order"):
        parts.append(_disp(commands["orders"][parsed["order"]["name"]], lang))
    desc = " · ".join(parts) if parts else "?"
    if parsed.get("target"):
        tgt = _disp(commands["groups"][parsed["target"]["name"]], lang)
        if parsed.get("order") and parsed["order"]["name"] == "protect":
            desc += f" → {tgt}"        # 护的是自己人, 不需要准星
        else:
            aim = "target (aim at them!)" if lang == "en" else "目标(需准星锁定)"
            desc += f" → {tgt} [{aim}]"
    return desc


class App:
    def __init__(self, settings, commands, overlay=None):
        c = settings["control"]
        self.settings = settings
        self.commands = commands
        self.overlay = overlay
        self.lang = settings["stt"].get("language", "zh")
        self._publish_lang()
        self.mode = c.get("mode", "continuous")
        self.ptt = c.get("push_to_talk_key", "caps lock")
        self.reload_key = c.get("reload_key") or ""
        self.toggle_key = c.get("listen_toggle_key") or ""
        self.auto_battle_gate = c.get("auto_battle_gate", False)
        self.prefixes = c.get("command_prefix") or []
        # 监听门: 手动开关 + 战斗自动门。listen_on=手动状态; battle_on=模组报的战斗中
        self.listen_on = True
        self.battle_on = not self.auto_battle_gate   # 不开自动门时恒真
        self.dry_run = "--dry-run" in sys.argv
        self.samplerate = settings["audio"]["samplerate"]
        self.silence_rms = settings["audio"].get("silence_rms", 0.006)
        self.slow_warn_sec = settings["stt"].get("slow_warn_sec", 3.0)
        self.matcher = Matcher.from_config(commands, c, lang=self.lang)
        self.retry = self._make_retry(c)
        ml = settings.get("modlink") or {}
        self.modlink = (ModLink(port=ml.get("port", 35127))
                        if ml.get("enabled", True) else None)
        if self.modlink:
            print(f"[模组桥] 端口 {self.modlink.port}: 点名目标/打最近的 会先走"
                  f"游戏内模组(真锁定), 连不上自动退回按键+准星。")
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
        self.fast = self._make_fast(settings, commands)
        from donation import Donation
        self.donation = Donation(settings)
        if self.donation.enabled:
            print("[共建] 语音数据共建已开启: 只保存执行了的指令片段, "
                  "存本机, 导出才离开电脑。")
        self._report_fun_pack()
        self.running = True

    @staticmethod
    def _report_fun_pack():
        import dictionary
        pack = dictionary.active_fun_pack()
        if not pack:
            return
        data = dictionary.load_fun_pack(pack)
        if data is None:
            return  # load_commands 已打过警告
        n = sum(len(v if isinstance(v, list) else v.get("aliases", []))
                for sec in ("groups", "orders")
                for v in (data.get(sec) or {}).values())
        print(f"[整活] 已激活整活包「{pack}」: {n} 条猎奇说法生效 "
              f"(切包改 settings 的 fun.pack 后按 F10)。")

    def _make_fast(self, settings, commands):
        """stt.engine=hybrid 时装配快路(流式ASR); 任何缺失都退回纯 Whisper。

        快路只开中文: 英文热词还没做, 且该模型英文质量未验证。
        """
        if settings["stt"].get("engine", "whisper") != "hybrid":
            return None
        if self.lang != "zh":
            print("[快路] 英文模式暂不启用快路, 使用纯 Whisper。")
            return None
        import stream_asr
        ok, why = stream_asr.available()
        if not ok:
            print(f"[快路] 不可用({why}), 退回纯 Whisper。")
            return None
        try:
            fast = stream_asr.FastTranscriber(self.commands)
        except Exception as e:
            print(f"[快路] 加载失败({e}), 退回纯 Whisper。")
            return None
        print("[快路] 流式引擎就绪: 命令~0.1s直出, 解不出时 Whisper 兜底。")
        return fast

    def _transcribe(self, audio, hotwords):
        """混合识别: 快路文本能解析出可执行指令 => 直出; 否则 Whisper 兜底。

        判据是"整条链路走得通"(前缀+聊天过滤+阈值), 不是裸文本像不像 ——
        快路听岔时兜底的 Whisper 常能救回(线阵/圆阵实测如此)。
        返回 (文本, 引擎标签)。
        """
        if self.fast:
            try:
                ftext = self.fast.transcribe(audio, self.samplerate)
            except Exception as e:
                print(f"    [快路] ⚠ 识别异常({e}), 本条走 Whisper")
                ftext = ""
            if ftext:
                armed, cleaned = self._check_prefix(ftext)
                if armed:
                    boost, _ = self.retry.boost_for(cleaned)
                    if self.matcher.parse(cleaned, boost=boost):
                        return ftext, "快路"
        return self.transcriber.transcribe(audio, hotwords=hotwords), "Whisper"

    @staticmethod
    def _make_retry(c):
        return RetryMemory(window_sec=c.get("retry_window_sec", 8.0),
                           cooldown_sec=c.get("repeat_cooldown_sec", 2.5),
                           bonus=c.get("retry_bonus", 12),
                           enabled=c.get("retry_boost", True))

    def _near(self, cand, threshold):
        """explain 的候选 -> {key: 别名}, 仅"差点命中"(没过线但加分够得着)。"""
        if not cand or cand["pass"]:
            return {}
        if cand["score"] < threshold - 2 * self.retry.bonus:
            return {}
        return {cand["name"]: cand["alias"]}

    def _try_modlink(self, parsed, g_key, o_key):
        """点名目标("骑兵进攻弓箭手")或打最近的 -> 走伴侣模组真锁定。

        成功返回 True(不再发按键); 模组没装/没开战斗/回 err 则返回 False,
        退回按键+准星方案 —— 模组是增强, 不是依赖。
        """
        if not self.modlink:
            return False
        odata = self.commands["orders"].get(o_key) or {}
        target = odata.get("modlink_target") or (
            parsed["target"]["name"] if parsed.get("target") else None)
        if not target:
            return False
        if self.dry_run:
            print(f"    ⚙ [dry-run] 若模组在线将执行: attack {g_key or 'all'} {target}")
            return False
        r = self.modlink.attack(g_key, target)
        if r and r.startswith("ok"):
            print(f"    ⚙ 模组锁定: {r}")
            return True
        if r:
            print(f"    ⚙ 模组不可执行({r}), 退回按键方案")
        else:
            # 静默降级是排错噩梦: 连不上也要大声说出来
            print("    ⚙ 模组未连接(游戏没开/模组没启用/不在战斗中), "
                  "退回按键+准星方案")
        return False

    # 左右半队支持的"派遣"指令 -> 模组 sideorder 令牌 (命令key 与模组用词对齐)
    _SIDE_ORDERS = {"charge": "charge", "advance": "advance",
                    "follow_me": "follow", "halt": "halt",
                    "fall_back": "fallback", "retreat": "retreat"}
    _SPLIT_CLASSES = ("infantry", "archers", "cavalry", "horse_archers")
    # 战术层(FormationAI, 需模组): 命令key -> 模组 tactic 动词
    _TACTICS = {"flank": "flank", "reclaim": "manual",
                "hold_high_ground": "highground", "skirmish": "skirmish",
                "cautious_advance": "cautious", "protect": "protect"}

    def _do_formation_cmd(self, g_key, o_key, desc, text, t_stt, engine,
                          t_key=""):
        """分队 / 左右半队 / 第N队 —— 走模组, 无按键退路。返回是否真正执行成功。"""
        if self.dry_run:
            print(f"    ⚙ [dry-run] 分队指令: {desc}")
            return False
        if not self.modlink:
            print("    ⚙ 分队/左右指挥需要伴侣模组(游戏没开/模组没启用)")
            self._set(t("⚙ 需要模组"), t("游戏没开或模组没启用"), "#ffb37f")
            return False
        desc2 = desc     # 定向进攻时下面会补上目标, 让浮层/横幅显示"打谁"
        if o_key in self._TACTICS:
            # 战术层: 兵种或全军("骑兵绕后"/"全军听令"); 左右半队/第N队暂不支持
            cls = g_key if g_key in self._SPLIT_CLASSES + ("all",) else None
            if not cls:
                print("    ⚙ 战术指令要指定兵种或全军, 例:「骑兵绕后」「全军听令」")
                self._set(t("⚙ 要指定兵种或全军"), t("例：骑兵绕后"), "#ffb37f")
                return False
            if o_key == "protect":
                # 护弓只认"弓箭手"目标: 没目标多半是噪音蹭到"保护"(如"招呼"),
                # 目标是别的兵种游戏里没有对应行为 —— 都不执行, 免得乱交 AI。
                if t_key != "archers":
                    print("    ⚙ 护卫指令只支持护弓箭手, 例:「骑兵保护弓箭手」")
                    self._set(t("⚙ 只支持护弓箭手"), t("例：骑兵保护弓箭手"), "#ffb37f")
                    return False
                if cls == "archers":
                    print("    ⚙ 弓箭手不能护自己, 换个兵种:「步兵保护弓箭手」")
                    self._set(t("⚙ 弓箭手不能护自己"), t("例：步兵保护弓箭手"), "#ffb37f")
                    return False
            r = self.modlink.tactic(cls, self._TACTICS[o_key])
        elif o_key == "split":
            if g_key not in self._SPLIT_CLASSES:
                print("    ⚙ 分队要指定具体兵种, 例:「骑兵分队」")
                self._set(t("⚙ 分队要指定兵种"), t("例：骑兵分队"), "#ffb37f")
                return False
            r = self.modlink.split(g_key)
        elif g_key.startswith("form"):        # 第N队 (form5..form8)
            tok = self._SIDE_ORDERS.get(o_key)
            if not tok:
                return self._side_unsupported(o_key)
            r = self.modlink.formorder(int(g_key[4:]), tok, t_key)
            desc2 = self._with_target(desc, o_key, t_key)
        else:  # cavalry_left / archers_right
            side = "left" if g_key.endswith("_left") else "right"
            cls = g_key[:-5] if side == "left" else g_key[:-6]
            tok = self._SIDE_ORDERS.get(o_key)
            if not tok:
                return self._side_unsupported(o_key)
            r = self.modlink.sideorder(cls, side, tok, t_key)
            desc2 = self._with_target(desc, o_key, t_key)
        via = "mod"
        ok = bool(r and r.startswith("ok"))
        if ok:
            print(f"    ✓ 听到「{text}」→ {desc2} · 模组直达 [{r}]")
            self._set(f"✓ {desc2}", t("听到: {t}").format(t=text), "#7dff9b")
        elif r:
            reason = {"not_split": "还没分队(先喊'骑兵分队')",
                      "too_few": "这队人太少, 分不了",
                      "empty_formation": "这个队现在没兵(先分队或换个队号)",
                      "bad_slot": "队号要在 1-8 之间",
                      "no_empty_slot": "编队槽满了(最多分出4支), 新战斗才清空",
                      "no_battle": "不在战斗中"}.get(r.replace("err ", ""), r)
            print(f"    ⚙ 分队未执行: {reason}")
            self._set(t("⚙ 分队未执行"), reason, "#ffb37f")
            via = "mod_err"
        else:
            print("    ⚙ 模组未连接(游戏没开/不在战斗)")
            self._set(t("⚙ 模组未连接"), t("游戏没开或不在战斗"), "#ffb37f")
            via = "mod_off"
        usage.record(self.lang, "ok" if ok else "miss",
                     g_key, o_key, via, t_stt, text,
                     engine if self.fast else "", t_key)
        return ok

    def _publish_lang(self):
        """把当前语言写到 %LOCALAPPDATA%/BannerlordVoice/lang.txt, 游戏内模组据此
        决定横幅/战斗记录用中文还是英文(源码/打包形态都写同一处, 模组只认这里)。"""
        try:
            from paths import log_dir
            p = os.path.join(os.path.dirname(log_dir()), "lang.txt")
            with open(p, "w", encoding="utf-8") as f:
                f.write(self.lang)
        except Exception as e:
            print(f"    ⚙ 写 lang.txt 失败(模组横幅将保持中文): {e}")

    def _side_unsupported(self, o_key):
        """左右队/第N队收到不支持的指令(如定点移动去那儿) —— 提示并返回失败。"""
        print(f"    ⚙ 左右/第N队暂不支持「{o_key}」"
              "(仅冲锋/进攻/前进/跟随/待命/后退/撤退; 定点移动用'跟我'把它们唤到身边)")
        self._set(t("⚙ 左右队暂不支持这条"),
                  t("仅冲锋/前进/跟随/待命/后退/撤退；定点移动用'跟我'"), "#ffb37f")
        return False

    def _with_target(self, desc, o_key, t_key):
        """定向进攻时把'→ 目标兵种'补进描述, 让状态明确是定向而非简单冲锋。"""
        if o_key == "charge" and t_key:
            tgt = _disp(self.commands["groups"][t_key], self.lang)
            arrow = " → 进攻敌方" if self.lang == "zh" else " → attacking enemy "
            return desc.split(" → ")[0] + arrow + tgt
        return desc

    def _set(self, status, detail="", color="#FFFFFF"):
        print(f"  {status}  {detail}")
        if self.overlay:
            self.overlay.push(status, detail, color)

    def _idle(self, detail=""):
        # 监听门关着: 明确显示静音原因, 让主播/观众知道现在不收指令
        if not self._gate_open():
            if not self.listen_on:
                self._set(t("🔇 已关闭识别"),
                          t("按 [{k}] 开启").format(k=self.toggle_key.upper()),
                          "#9aa4ad")
            else:
                self._set(t("🔇 战斗外静音"), t("进入战斗自动开启"), "#9aa4ad")
            return
        if self.mode == "continuous":
            self._set(t("👂 监听中…"), detail or t("说出指令即可"), "#7Fd1ff")
        else:
            self._set(t("待命中…"), detail or t("按住 [{k}] 说话").format(k=self.ptt),
                      "#7Fd1ff")

    def reload_config(self):
        """热重载词典/阈值到运行中的引擎 (Whisper 模型不动)。热键回调。"""
        try:
            settings, commands = load_cfg()
        except Exception as e:
            self._set(t("⚠ 词典重载失败"), f"YAML: {e}", "#ff8a8a")
            return
        c = settings["control"]
        self.commands = commands
        self.matcher = Matcher.from_config(commands, c, lang=self.lang)
        self.retry = self._make_retry(c)
        ml = settings.get("modlink") or {}
        self.modlink = (ModLink(port=ml.get("port", 35127))
                        if ml.get("enabled", True) else None)
        self.executor = Executor(settings, commands, dry_run=self.dry_run)
        self.prefixes = c.get("command_prefix") or []
        self.silence_rms = settings["audio"].get("silence_rms", self.silence_rms)
        if self.fast:
            try:
                self.fast.rebuild(commands)  # 热词跟着新词典走
            except Exception as e:
                print(f"[快路] ⚠ 热词重建失败({e}), 快路继续用旧热词。")
        from donation import Donation
        self.donation = Donation(settings)  # 共建开关热生效(启动器改完按F10)
        self._report_fun_pack()             # 整活包切换热生效
        n = sum(len(d.get("aliases", []))
                for sec in ("groups", "orders")
                for d in commands.get(sec, {}).values())
        print(f"[重载] 词典已刷新: {n} 条别名, 立即生效。")
        self._set(t("🔄 词典已重载"), t("{n} 条说法已生效").format(n=n), "#7dff9b")

    def _register_reload_hotkey(self):
        if not self.reload_key:
            return
        try:
            keyboard.add_hotkey(self.reload_key, self.reload_config)
            print(f"[重载] 按 [{self.reload_key.upper()}] 可热重载词典 (改完不用重启)。")
        except Exception as e:
            print(f"[重载] ⚠ 热键 {self.reload_key} 注册失败: {e}")

    def _register_toggle_hotkey(self):
        if not self.toggle_key:
            return
        try:
            keyboard.add_hotkey(self.toggle_key, self._toggle_listen)
            print(f"[监听] 按 [{self.toggle_key.upper()}] 可开/关命令识别 "
                  f"(直播聊天时关掉防误触)。")
        except Exception as e:
            print(f"[监听] ⚠ 开关键 {self.toggle_key} 注册失败: {e}")

    def _toggle_listen(self):
        self.listen_on = not self.listen_on
        state = "开" if self.listen_on else "关"
        print(f"[监听] 命令识别已{state}。")
        self._idle()

    def _register_review_hotkey(self):
        key = self.settings["control"].get("review_key") or ""
        if not key:
            return
        try:
            keyboard.add_hotkey(key, self._open_review)
            print(f"[复盘] 按 [{key.upper()}] 打开指令复盘 (逐条看识别/纠错绑定)。")
        except Exception as e:
            print(f"[复盘] ⚠ 热键 {key} 注册失败: {e}")

    def _open_review(self):
        """游戏里发现错配 -> 按键呼出复盘目录, 当场改绑定。独立进程, 不卡识别。"""
        import subprocess
        from paths import FROZEN
        if FROZEN:
            cmd = [sys.executable, "--mode", "review"]
        else:
            pyw = sys.executable.replace("python.exe", "pythonw.exe")
            cmd = [pyw if os.path.exists(pyw) else sys.executable,
                   os.path.join(ROOT, "src", "app.py"), "--mode", "review"]
        try:
            subprocess.Popen(cmd)
            print("[复盘] 指令复盘窗口已打开。")
        except Exception as e:
            print(f"[复盘] ⚠ 打开失败: {e}")

    def _gate_open(self):
        """现在该不该处理命令: 手动开着 且 (没开自动门 或 在战斗中)。"""
        return self.listen_on and self.battle_on

    def _battle_gate_poll(self):
        """后台轮询伴侣模组: ping 通=在战斗中(模组的 socket 只在战斗开)。"""
        import threading
        import time as _t

        def loop():
            while self.running:
                on = bool(self.modlink and self.modlink.ping())
                if on != self.battle_on:
                    self.battle_on = on
                    print(f"[监听] 战斗自动门: {'进入战斗, 开始识别' if on else '离开战斗, 已静音'}")
                    self._idle()
                _t.sleep(2.0)

        threading.Thread(target=loop, daemon=True).start()

    def _debug(self, text):
        """更新浮层底部常驻 debug 行 (上一条发生了什么)。"""
        if self.overlay:
            self.overlay.push_debug(text)

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
        # 监听门关着(手动关 或 不在战斗) => 连识别都不做, 省算力也防误触
        if not self._gate_open():
            self._idle()
            return
        t_seg = time.perf_counter()
        secs = audio.shape[0] / self.samplerate
        print(f"[{time.strftime('%H:%M:%S')}] 🎧 捕到语音 {secs:.1f}s")

        rms = float(np.sqrt(np.mean(audio ** 2)))
        if rms < self.silence_rms:
            self._idle("(没听到声音)")
            return

        self._set(t("识别中…"), "", "#c9a0ff")
        # 重试窗口内: 把上次差点命中的说法喂给识别器, 偏置这一遍听准
        hotwords = self.retry.hotwords()
        t0 = time.perf_counter()
        text, engine = self._transcribe(audio, hotwords)
        t_stt = time.perf_counter() - t0
        eng = f"[{engine}]" if self.fast else ""
        if t_stt > self.slow_warn_sec:
            print(f"    [⚠ 识别偏慢] {t_stt:.1f}s (音频 {secs:.1f}s) "
                  f"—— 多半是游戏在抢 GPU, 试试游戏内锁帧/关游戏模式")
        if not text:
            print(f"    ✗ 没听清（识别 {t_stt:.2f}s，可能太轻/太快）")
            self._debug(t("上一条 ✗ 没听清（识别 {s}s）").format(s=f"{t_stt:.1f}"))
            self._idle(t("(没听清)"))
            return

        armed, cleaned = self._check_prefix(text)
        if not armed:
            print(f"    · 听到「{text}」→ 无口令前缀, 忽略（识别 {t_stt:.2f}s）")
            self._debug(t("上一条 · 听到「{t}」→ 无口令前缀, 忽略").format(t=text))
            self._idle(t("听到: {t}").format(t=text))
            return

        boost, boost_why = self.retry.boost_for(cleaned)
        tr = self.matcher.explain(cleaned, boost=boost)
        parsed = tr["result"]
        if not parsed:
            # 记住差点命中的候选: 用户若马上重说一遍, 就定向放大它们
            self.retry.note_miss(
                cleaned,
                self._near(tr["group"], self.matcher.group_threshold),
                self._near(tr["order"], self.matcher.order_threshold))
            print(f"    ✗ 听到「{text}」→ 未匹配/聊天, 未执行"
                  f"（识别 {t_stt:.2f}s{eng}）")
            usage.record(self.lang, "miss", None, None, "", t_stt, text,
                         engine if self.fast else "")
            self.donation.save(audio, self.samplerate, "miss", None, None,
                               text, engine)
            self._debug(t("上一条 ✗ 听到「{t}」→ 未匹配/聊天, 未执行").format(t=text))
            self._set(t("未匹配"), t("听到: {t}").format(t=text), "#ff8a8a")
            time.sleep(0.6)
            self._idle()
            return

        desc = describe(parsed, self.commands, self.lang)
        keys = ([parsed["group"]["select"]] if parsed["group"] else []) + \
               (parsed["order"]["keys"] if parsed["order"] else [])
        g_key = parsed["group"]["name"] if parsed["group"] else None
        o_key = parsed["order"]["name"]
        # 回声抑制: 冷却期内解析出同一条指令, 多半是回音/黏连, 不再发键
        if self.retry.is_echo(g_key, o_key):
            print(f"    ⏸ 听到「{text}」→ {desc}: 冷却期内与刚执行的相同, "
                  f"判为回声/黏连, 忽略")
            self._debug(t("上一条 ⏸ 回声抑制「{t}」").format(t=text))
            self._idle()
            return
        if boost_why:
            print(f"    🔁 {boost_why}")
        # 分队 / 左右半队 / 第N队 / 战术层(绕后/听令): 纯模组指令, 单独路由
        is_side = bool(g_key) and (g_key.endswith("_left")
                                   or g_key.endswith("_right"))
        is_form = bool(g_key) and g_key.startswith("form") and g_key[4:].isdigit()
        if o_key == "split" or o_key in self._TACTICS or is_side or is_form:
            t_key = parsed["target"]["name"] if parsed.get("target") else ""
            ok = self._do_formation_cmd(g_key, o_key, desc, text, t_stt,
                                        engine, t_key)
            # 只有真正执行了才记录/防回声 —— 否则被拒的指令(如左右队不支持
            # 定点移动)会把自己写进回声窗口, 重说反被误抑制(实战踩到)
            if ok:
                self.retry.note_exec(g_key, o_key)
            self._idle()
            return
        t0 = time.perf_counter()
        via_mod = self._try_modlink(parsed, g_key, o_key)
        if via_mod:
            desc = (desc.replace("[目标(需准星锁定)]", "[模组已锁定✓]")
                        .replace("[target (aim at them!)]", "[locked by mod]"))
        else:
            self.executor.execute(parsed)
            # 按键指令的战场回执: 推给模组打顶部快讯横幅 (定向进攻由模组
            # 自己播报更详细的, 不重复; 没模组/不在战斗则毫秒级静默失败)
            if self.modlink and not self.dry_run:
                self.modlink.notify(desc)
        t_key = parsed["target"]["name"] if parsed.get("target") else ""
        usage.record(self.lang, "ok", g_key, o_key,
                     "mod" if via_mod else "keys", t_stt, text,
                     engine if self.fast else "", t_key)
        self.donation.save(audio, self.samplerate, "ok", g_key, o_key,
                           text, engine, target=t_key)
        self.retry.note_exec(g_key, o_key)
        # 执行了但兵种没过线(只作用于当前选中编队): 记为差点命中 —— 用户若马上
        # 重说, 说明发错了对象, 下一遍放大该兵种 (专治 "all units"→"or units")
        if tr["group"] and not tr["group"]["pass"]:
            self.retry.note_miss(
                cleaned, self._near(tr["group"], self.matcher.group_threshold), {})
        t_keys = time.perf_counter() - t0
        total = time.perf_counter() - t_seg
        how = t("模组直达") if via_mod \
            else t("发键 {keys}").format(keys=" ".join(keys))
        print(f"    ✓ 听到「{text}」→ {desc} · {how}"
              f"（识别 {t_stt:.2f}s{eng} + 执行 {t_keys:.2f}s = 共 {total:.2f}s）")
        self._debug(t("上一条 ✓ 听到「{t}」→ {d} · {how}（{s}s）").format(
            t=text, d=desc, how=how, s=f"{t_stt:.1f}"))
        self._set(f"✓ {desc}", t("听到: {t}").format(t=text), "#7dff9b")

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
        self._register_toggle_hotkey()
        self._register_review_hotkey()
        if self.auto_battle_gate:
            print("[监听] 战斗自动门已开: 大地图/菜单静音, 进入战斗自动识别。")
            self._battle_gate_poll()
        if self.mode == "continuous":
            self.loop_continuous()
        else:
            self.loop_ptt()

    def stop(self):
        self.running = False
        if self.listener:
            self.listener.stop()
        for k in (self.reload_key, self.toggle_key):
            if k:
                try:
                    keyboard.remove_hotkey(k)
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
