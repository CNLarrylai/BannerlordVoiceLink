using TaleWorlds.MountAndBlade;

namespace BannerlordVoiceLink
{
    /// <summary>
    /// Entry point. Attaches the VoiceLink mission behavior to every mission,
    /// so the voice app can talk to us whenever a battle is running.
    /// </summary>
    public class VoiceLinkSubModule : MBSubModuleBase
    {
        public override void OnMissionBehaviorInitialize(Mission mission)
        {
            base.OnMissionBehaviorInitialize(mission);
            mission.AddMissionBehavior(new VoiceLinkBehavior());
        }
    }
}
