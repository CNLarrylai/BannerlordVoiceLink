using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using TaleWorlds.Core;
using TaleWorlds.MountAndBlade;

namespace BannerlordVoiceLink
{
    /// <summary>
    /// Localhost TCP bridge between the voice app (Python) and the battle.
    ///
    /// Protocol: one ASCII line per request, one line per reply.
    ///   ping                      -> "ok battle=1|0"
    ///   info                      -> "ok Ranged:80:142 Cavalry:40:200 ..." (enemy formations: class:units:dist)
    ///   attack <group> <target>   -> "ok attacked=N target=Ranged:80:142" or "err <reason>"
    ///     group : infantry|archers|cavalry|horse_archers|all
    ///     target: infantry|archers|cavalry|horse_archers|nearest
    ///
    /// Game API must run on the main thread, so the socket thread only queues
    /// requests; OnMissionTick drains and executes them (pattern used by
    /// existing mods, e.g. RTSCamera's command queue).
    /// </summary>
    public class VoiceLinkBehavior : MissionLogic
    {
        private const int Port = 35127;   // 语音程序 settings.yaml modlink.port 需一致
        private const int ReplyTimeoutMs = 1000;

        private TcpListener _listener;
        private Thread _thread;
        private volatile bool _running;

        private class Req
        {
            public string Line;
            public readonly BlockingCollection<string> Reply =
                new BlockingCollection<string>(1);
        }

        private readonly ConcurrentQueue<Req> _requests = new ConcurrentQueue<Req>();

        // ---------- lifecycle ----------

        public override void OnBehaviorInitialize()
        {
            base.OnBehaviorInitialize();
            _running = true;
            _thread = new Thread(ServerLoop) { IsBackground = true, Name = "VoiceLink" };
            _thread.Start();
        }

        public override void OnRemoveBehavior()
        {
            _running = false;
            try { _listener?.Stop(); } catch { }
            base.OnRemoveBehavior();
        }

        // ---------- socket thread ----------

        private void ServerLoop()
        {
            try
            {
                _listener = new TcpListener(IPAddress.Loopback, Port);
                _listener.Start();
            }
            catch
            {
                // Port taken (stale battle scene still shutting down) - stay silent.
                return;
            }
            while (_running)
            {
                TcpClient client = null;
                try
                {
                    client = _listener.AcceptTcpClient();
                    client.ReceiveTimeout = 2000;
                    client.SendTimeout = 2000;
                    using (var stream = client.GetStream())
                    using (var reader = new StreamReader(stream, Encoding.ASCII))
                    using (var writer = new StreamWriter(stream, Encoding.ASCII) { AutoFlush = true })
                    {
                        var line = reader.ReadLine();
                        if (line == null)
                            continue;
                        var req = new Req { Line = line.Trim() };
                        _requests.Enqueue(req);
                        string reply;
                        if (!req.Reply.TryTake(out reply, ReplyTimeoutMs))
                            reply = "err timeout";
                        writer.WriteLine(reply);
                    }
                }
                catch
                {
                    // Listener stopped or client dropped; keep serving.
                }
                finally
                {
                    try { client?.Close(); } catch { }
                }
            }
        }

        // ---------- main thread ----------

        public override void OnMissionTick(float dt)
        {
            base.OnMissionTick(dt);
            Req req;
            while (_requests.TryDequeue(out req))
            {
                string reply;
                try { reply = Handle(req.Line); }
                catch (Exception e) { reply = "err " + e.GetType().Name; }
                req.Reply.TryAdd(reply);
            }
        }

        private string Handle(string line)
        {
            var parts = line.Split(new[] { ' ' }, StringSplitOptions.RemoveEmptyEntries);
            if (parts.Length == 0)
                return "err empty";
            switch (parts[0])
            {
                case "ping":
                    return "ok battle=" + (InBattle() ? "1" : "0");
                case "info":
                    return Info();
                case "attack":
                    return parts.Length < 3
                        ? "err usage: attack <group> <target>"
                        : Attack(parts[1], parts[2]);
                default:
                    return "err unknown_cmd";
            }
        }

        private bool InBattle()
        {
            var m = Mission.Current;
            return m != null && m.PlayerTeam != null && !m.MissionEnded;
        }

        private static bool TryClass(string name, out FormationClass fc)
        {
            switch (name)
            {
                case "infantry": fc = FormationClass.Infantry; return true;
                case "archers": fc = FormationClass.Ranged; return true;
                case "cavalry": fc = FormationClass.Cavalry; return true;
                case "horse_archers": fc = FormationClass.HorseArcher; return true;
                default: fc = FormationClass.Infantry; return false;
            }
        }

        private List<Formation> EnemyFormations()
        {
            var res = new List<Formation>();
            var mission = Mission.Current;
            var player = mission.PlayerTeam;
            foreach (Team team in mission.Teams)
            {
                if (team == null || !team.IsEnemyOf(player))
                    continue;
                foreach (Formation f in team.FormationsIncludingEmpty)
                    if (f != null && f.CountOfUnits > 0)
                        res.Add(f);
            }
            return res;
        }

        private string Info()
        {
            if (!InBattle())
                return "err no_battle";
            var me = Mission.Current.MainAgent;
            var pos = me != null
                ? me.Position.AsVec2
                : Mission.Current.PlayerTeam.GeneralAgent?.Position.AsVec2
                  ?? TaleWorlds.Library.Vec2.Zero;
            var sb = new StringBuilder("ok");
            foreach (var f in EnemyFormations())
            {
                sb.Append(' ').Append(f.FormationIndex)
                  .Append(':').Append(f.CountOfUnits)
                  .Append(':').Append((int)f.CurrentPosition.Distance(pos));
            }
            return sb.ToString();
        }

        private string Attack(string groupName, string targetName)
        {
            if (!InBattle())
                return "err no_battle";
            var player = Mission.Current.PlayerTeam;

            // 1. resolve own formations to command
            var groups = new List<Formation>();
            if (groupName == "all")
            {
                foreach (var fc in new[] { FormationClass.Infantry, FormationClass.Ranged,
                                           FormationClass.Cavalry, FormationClass.HorseArcher })
                {
                    var f = player.GetFormation(fc);
                    if (f != null && f.CountOfUnits > 0)
                        groups.Add(f);
                }
            }
            else
            {
                FormationClass gc;
                if (!TryClass(groupName, out gc))
                    return "err bad_group";
                var f = player.GetFormation(gc);
                if (f == null || f.CountOfUnits == 0)
                    return "err group_empty";
                groups.Add(f);
            }
            if (groups.Count == 0)
                return "err group_empty";

            // 2. resolve target filter
            var byClass = false;
            FormationClass tc = FormationClass.Infantry;
            if (targetName != "nearest")
            {
                if (!TryClass(targetName, out tc))
                    return "err bad_target";
                byClass = true;
            }

            var enemies = EnemyFormations();
            if (enemies.Count == 0)
                return "err no_enemies";

            // 3. each commanded formation charges its own best-matching target
            //    (same call chain the game/RTSCamera use for click-targeted charge)
            var done = 0;
            var lastDesc = "";
            foreach (var g in groups)
            {
                Formation best = null;
                var bestD = float.MaxValue;
                foreach (var e in enemies)
                {
                    if (byClass && e.FormationIndex != tc)
                        continue;
                    var d = g.CurrentPosition.Distance(e.CurrentPosition);
                    if (d < bestD) { bestD = d; best = e; }
                }
                if (best == null)
                    continue;
                g.SetMovementOrder(MovementOrder.MovementOrderChargeToTarget(best));
                g.SetTargetFormation(best);
                done++;
                lastDesc = best.FormationIndex + ":" + best.CountOfUnits + ":" + (int)bestD;
            }
            return done == 0
                ? "err target_not_found"
                : "ok attacked=" + done + " target=" + lastDesc;
        }
    }
}
