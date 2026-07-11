"""版本与发布信息 —— 单一出处, 方便将来做更新检查/强制最低版本。"""

APP_NAME = "骑砍语音指挥"
APP_EN = "Bannerlord Voice Commander"
APP_VERSION = "0.8.6"   # 0.8.6: 光喊左右队=最近分的队; 横幅报新队第几队; no_empty_slot友好提示

# dev / free / pro —— 打包分发时可改; 现在都当全功能
BUILD_CHANNEL = "dev"


def check_for_updates():
    """更新检查桩。将来: 请求 version.json 比对, 返回新版本信息或 None。"""
    return None
