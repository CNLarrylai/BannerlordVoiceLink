"""授权 / 功能分档 —— 变现接缝。

现在是"全解锁"的桩: 所有功能都开、档位是 pro。将来加订阅/买断时,
只需把 _resolve() 换成"读本地授权文件 + 在线激活校验 + 机器绑定",
功能代码 (调 feature_enabled / is_pro) 一行都不用改。

用法(功能侧):
    from license import LICENSE
    if LICENSE.feature_enabled("multi_game_profiles"):
        ...
"""
from machine_id import machine_id
from version import BUILD_CHANNEL

# 功能清单: 将来把要收费的功能名列在这里, 按档位开关。
# 现在全部对所有档开放。
FEATURES_BY_TIER = {
    "free": {"core_voice", "command_dict", "audio_setup"},
    "pro": {"*"},  # 全部
}


class LicenseManager:
    def __init__(self):
        self._tier, self._info = self._resolve()

    def _resolve(self):
        """现在: 直接全解锁。将来: 读授权文件 + 在线校验 + 校验机器绑定。"""
        # 未来大致长这样:
        #   lic = load_local_license()
        #   if lic and verify_online(lic, machine_id()): return lic.tier, lic
        return "pro", {"source": "unlicensed-dev", "machine": machine_id()}

    @property
    def tier(self):
        return self._tier

    def is_pro(self):
        return self._tier == "pro"

    def feature_enabled(self, feature: str) -> bool:
        allowed = FEATURES_BY_TIER.get(self._tier, set())
        return "*" in allowed or feature in allowed

    def status_line(self):
        return f"授权档位: {self._tier} (渠道 {BUILD_CHANNEL}, 未启用付费校验)"


LICENSE = LicenseManager()
