using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using TaleWorlds.MountAndBlade;

namespace BannerlordVoiceLink
{
    /// <summary>
    /// Entry point. Attaches the VoiceLink mission behavior to every mission,
    /// and auto-starts the bundled voice app (VoiceApp\BannerlordVoice.exe)
    /// when the mod is distributed with it (Steam Workshop one-click setup).
    /// </summary>
    public class VoiceLinkSubModule : MBSubModuleBase
    {
        private bool _autostartTried;

        protected override void OnSubModuleLoad()
        {
            base.OnSubModuleLoad();
            VoiceLinkBehavior.Beacon("模组已被游戏加载 (OnSubModuleLoad)");
        }

        protected override void OnBeforeInitialModuleScreenSetAsRoot()
        {
            base.OnBeforeInitialModuleScreenSetAsRoot();
            if (_autostartTried)
                return;
            _autostartTried = true;
            TryAutostartVoiceApp();
        }

        public override void OnMissionBehaviorInitialize(Mission mission)
        {
            base.OnMissionBehaviorInitialize(mission);
            mission.AddMissionBehavior(new VoiceLinkBehavior());
        }

        /// <summary>
        /// 随模组分发的语音程序自动启动: 模组目录/VoiceApp/BannerlordVoice.exe。
        /// 没带 VoiceApp(本地开发模式)/已在运行/被 autostart_off.txt 关闭时跳过。
        /// 工坊订阅者的体验: 订阅 -> 启用模组 -> 开游戏 -> 语音面板自己出现。
        /// </summary>
        private static void TryAutostartVoiceApp()
        {
            try
            {
                var dll = Assembly.GetExecutingAssembly().Location;
                var moduleRoot = Path.GetFullPath(Path.Combine(
                    Path.GetDirectoryName(dll), "..", ".."));
                var appDir = Path.Combine(moduleRoot, "VoiceApp");
                var exe = Path.Combine(appDir, "BannerlordVoice.exe");
                if (!File.Exists(exe))
                {
                    VoiceLinkBehavior.Beacon("VoiceApp 未随模组分发(开发模式), 不自动启动");
                    return;
                }
                // 关闭开关有两处: 随包目录(整包级) 和 用户目录(个人级, 不会被
                // 模组更新/重装覆盖 —— 开发者本人用源码版时放这里最合适)
                var userOff = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "BannerlordVoice", "autostart_off.txt");
                if (File.Exists(Path.Combine(appDir, "autostart_off.txt"))
                    || File.Exists(userOff))
                {
                    VoiceLinkBehavior.Beacon("autostart_off 开关存在, 跳过自动启动");
                    return;
                }
                if (Process.GetProcessesByName("BannerlordVoice").Length > 0)
                {
                    VoiceLinkBehavior.Beacon("语音程序已在运行, 无需自动启动");
                    return;
                }
                Process.Start(new ProcessStartInfo
                {
                    FileName = exe,
                    WorkingDirectory = appDir,
                    UseShellExecute = true,   // exe 带 UAC 清单, 必须走 shell
                });
                VoiceLinkBehavior.Beacon("已自动启动语音程序: " + exe);
            }
            catch (Exception e)
            {
                VoiceLinkBehavior.Beacon("自动启动语音程序失败: " + e.Message);
            }
        }
    }
}
