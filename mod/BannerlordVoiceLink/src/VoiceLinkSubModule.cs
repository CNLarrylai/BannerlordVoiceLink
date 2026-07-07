using TaleWorlds.MountAndBlade;

namespace BannerlordVoiceLink
{
    /// <summary>
    /// Entry point. Attaches the VoiceLink mission behavior to every mission,
    /// so the voice app can talk to us whenever a battle is running.
    /// </summary>
    public class VoiceLinkSubModule : MBSubModuleBase
    {
        protected override void OnSubModuleLoad()
        {
            base.OnSubModuleLoad();
            VoiceLinkBehavior.Beacon("模组已被游戏加载 (OnSubModuleLoad)");
        }

        public override void OnMissionBehaviorInitialize(Mission mission)
        {
            base.OnMissionBehaviorInitialize(mission);
            mission.AddMissionBehavior(new VoiceLinkBehavior());
        }
    }
}
