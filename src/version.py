"""版本与发布信息 —— 单一出处, 方便将来做更新检查/强制最低版本。"""

APP_NAME = "骑砍语音指挥"
APP_EN = "Bannerlord Voice Commander"
APP_VERSION = "0.9.10"  # 0.9.10: 选队改按真实兵种成分(模组名册), 缺兵种不再误发成全军令
                        # 0.9.9: 监听三模式(一直监听/按键开关/按住说话)+改键; 设置改动埋点(本地)
                        # 0.9.8: 模型下载重写(测速择优/续传换源/sha256), 修国内卡在 hf-mirror 美国 CDN
                        # 0.9.7: 英文 attack them/get them/kill them 归就近集火(对齐中文"打他们")
                        # 0.9.6: 修打包版选 turbo 静默回退 small(缓存仓库名写死 Systran)
                        # 0.9.5: 英文识别加固(All->Or 口音容错/按词算占比/短噪音不误触)
                        # 0.9.4: 手动放模型支持简易目录 %LOCALAPPDATA%\BannerlordVoice\models\<名>

# dev / free / pro —— 打包分发时可改; 现在都当全功能
BUILD_CHANNEL = "dev"


def check_for_updates():
    """更新检查桩。将来: 请求 version.json 比对, 返回新版本信息或 None。"""
    return None
