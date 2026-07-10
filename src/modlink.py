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

    def attack(self, group, target):
        """group: infantry/archers/cavalry/horse_archers/all (None 视为 all);
        target: 同类名 或 nearest。返回模组回复("ok ..."/"err ...") 或 None。"""
        return self._send(f"attack {group or 'all'} {target}")

    def notify(self, text):
        """把一条指令描述推给游戏顶部快讯横幅 (纯播报, 失败无所谓)。"""
        return self._send(f"notify {text}")
