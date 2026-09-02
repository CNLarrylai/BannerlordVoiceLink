"""版本与发布信息 —— 单一出处, 方便将来做更新检查/强制最低版本。"""

APP_NAME = "骑砍语音指挥"
APP_EN = "Bannerlord Voice Commander"
APP_VERSION = "0.9.6"   # 0.9.6: 修打包版选 turbo 静默回退 small(缓存仓库名写死 Systran)
                        # 0.9.5: 英文识别加固(All->Or 口音容错/按词算占比/短噪音不误触)
                        # 0.9.4: 手动放模型支持简易目录 %LOCALAPPDATA%\BannerlordVoice\models\<名>

# dev / free / pro —— 打包分发时可改; 现在都当全功能
BUILD_CHANNEL = "dev"


def check_for_updates():
    """更新检查桩。将来: 请求 version.json 比对, 返回新版本信息或 None。"""
    return None
