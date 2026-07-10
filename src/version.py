"""版本与发布信息 —— 单一出处, 方便将来做更新检查/强制最低版本。"""

APP_NAME = "骑砍语音指挥"
APP_EN = "Bannerlord Voice Commander"
APP_VERSION = "0.7.9"   # .9: 普通按键指令也上顶部横幅(notify协议, UTF-8)

# dev / free / pro —— 打包分发时可改; 现在都当全功能
BUILD_CHANNEL = "dev"


def check_for_updates():
    """更新检查桩。将来: 请求 version.json 比对, 返回新版本信息或 None。"""
    return None
