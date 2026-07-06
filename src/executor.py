"""按键注入 —— 用 DirectInput 把指令发给骑砍。"""
import time

import pydirectinput

pydirectinput.PAUSE = 0.0  # 由我们自己控制间隔


class Executor:
    def __init__(self, cfg: dict, commands: dict, dry_run: bool = False):
        c = cfg["control"]
        self.dry_run = dry_run
        self.key_delay = c.get("key_delay", 0.06)
        self.select_delay = c.get("select_delay", 0.12)

    def _press(self, key: str):
        if self.dry_run:
            print(f"      [dry-run] 按键: {key}")
        else:
            pydirectinput.press(key)
        time.sleep(self.key_delay)

    def execute(self, parsed: dict):
        """执行一条解析后的指令。"""
        group = parsed.get("group")
        order = parsed.get("order")
        if not order:
            return  # 只有兵种没指令 => 不发键, 免得乱切编队

        # 1) 先选编队 (如果指明了兵种)。全军=数字键 0, 普通编队=1~8, 都是单键。
        if group:
            self._press(group["select"])
            time.sleep(self.select_delay)

        # 2) 再下指令
        for k in order["keys"]:
            self._press(k)
