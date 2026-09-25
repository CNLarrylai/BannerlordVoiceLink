"""伴侣模组桥 —— 与游戏内 BannerlordVoiceLink 模组通信 (本机 TCP)。

模组(mod/BannerlordVoiceLink)在每场战斗中监听 127.0.0.1:35127, 纯文本行协议
(UTF-8, notify 要带中文):
  attack <group> <target>  让自家编队攻击特定敌方编队 (nearest=最近的)
  notify <文本>            在游戏顶部快讯横幅播报 (普通按键指令的战场回执)
  info / ping              战场信息 / 探活

没装模组、不在战斗、游戏没开 => 连接立即失败返回 None, 调用方退化到
按键+准星方案 —— 模组是增强, 不是依赖。
"""
import socket


class ModLink:
    def __init__(self, port=35127, enabled=True, timeout=0.25):
        self.port = int(port)
        self.enabled = enabled
        self.timeout = timeout

    def _send(self, line):
        if not self.enabled:
            return None
        try:
            with socket.create_connection(("127.0.0.1", self.port),
                                          timeout=self.timeout) as s:
                s.sendall((line + "\n").encode("utf-8"))
                # attack 在游戏下一帧 tick 执行后才回复, 读超时放宽一些
                s.settimeout(self.timeout + 1.0)
                f = s.makefile("r", encoding="utf-8", newline="\n")
                return (f.readline() or "").strip() or None
        except OSError:
            return None

    def ping(self):
        return self._send("ping")

    def info(self):
        return self._send("info")

    def roster(self):
        """编队名册: "ok infantry=1:120:i118,r2 archers=- cavalry=2:40:c40 ..."
        即 兵种=数字键:人数:成分, 缺的兵种报 '-'。数字键按**真实兵种成分**给,
        不按槽位号猜 —— 玩家改过"战斗部署"也不会指挥错人。见 roster.Roster。"""
        return self._send("roster")

    def select(self, group):
        """让模组直接选中某编队(不发数字键), 后面的 F 键就落在它身上。
        绕开游戏"按了空槽的键就选全军"那条分支。返回 "ok <键号>:<人数>"。"""
        return self._send(f"select {group}")

    def selected(self):
        """当前选中的编队(数字键号), 排错用: "ok 2" / "ok 1 2 3 4"。"""
        return self._send("selected")

    def attack(self, group, target):
        """group: infantry/archers/cavalry/horse_archers/all (None 视为 all);
        target: 同类名 或 nearest。返回模组回复("ok ..."/"err ...") 或 None。"""
        return self._send(f"attack {group or 'all'} {target}")

    def notify(self, text):
        """把一条指令描述推给游戏顶部快讯横幅 (纯播报, 失败无所谓)。"""
        return self._send(f"notify {text}")

    def split(self, group):
        """把某兵种一分为二 (原生 Formation.Split)。返回模组回复或 None。"""
        return self._send(f"split {group}")

    def sideorder(self, group, side, order, target=""):
        """指挥某兵种分出的左/右半队(左=原队, 右=新队)。
        group=兵种; side=left/right; order=charge/advance/follow/halt/fallback/
        retreat; target=敌方兵种(定向进攻, order=charge时有效, 空=简单冲锋)。
        返回模组回复("ok ..."/"err ...") 或 None。"""
        return self._send(f"sideorder {group} {side} {order} {target or '-'}")

    def formorder(self, slot, order, target=""):
        """按编队槽位号"第N队"指挥(slot 1-8)。order/target 同 sideorder。"""
        return self._send(f"formorder {slot} {order} {target or '-'}")

    def moverel(self, group, ward, side, dist):
        """相对站位(需模组): group 走到 ward(己方兵种, self=自己) 的 side(left/right/
        front/back) dist 米处, 一次性移动令, 不持续驱动。"""
        return self._send(f"moverel {group} {ward or 'self'} {side} {int(dist)}")

    def tactic(self, group, verb, target=""):
        """战术层(FormationAI): group=兵种/all; verb=flank(绕后)/highground(占高地)/
        skirmish(游击)/cautious(稳步推进)/protect|guardleft|guardright(护卫)/manual(收回)。
        target: 护卫时被护的己方兵种(archers/horse_archers/infantry/cavalry), 空=弓箭手。"""
        return self._send(f"tactic {group} {verb} {target}".rstrip())
