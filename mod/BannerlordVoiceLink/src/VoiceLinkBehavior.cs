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

        /// <summary>Liveness beacon: append to the voice app's log dir so we can
        /// tell "mod not loaded" from "not in battle" without guessing.</summary>
        internal static void Beacon(string msg)
        {
            try
            {
                var dir = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "BannerlordVoice", "logs");
                Directory.CreateDirectory(dir);
                File.AppendAllText(Path.Combine(dir, "mod.log"),
                    DateTime.Now.ToString("HH:mm:ss") + " " + msg + "\r\n");
            }
            catch
            {
                // 心跳失败不能影响游戏
            }
        }

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

        private bool _started;

        // 初始化顺序陷阱(反编译 Mission.AfterStart 确认): 子模组的
        // OnMissionBehaviorInitialize 在所有已有行为的 OnBehaviorInitialize 之后
        // 才被调用 —— 在那里 AddMissionBehavior 加入的行为, OnBehaviorInitialize
        // 永远不会被调用, 但 EarlyStart/AfterStart 会。两边都挂 + 一次性开关。
        public override void OnBehaviorInitialize()
        {
            base.OnBehaviorInitialize();
            StartServer("OnBehaviorInitialize");
        }

        public override void AfterStart()
        {
            base.AfterStart();
            StartServer("AfterStart");
        }

        private void StartServer(string via)
        {
            if (_started)
                return;
            _started = true;
            Beacon("战斗开始(" + via + "), 启动监听线程");
            _running = true;
            _thread = new Thread(ServerLoop) { IsBackground = true, Name = "VoiceLink" };
            _thread.Start();
        }

        public override void OnRemoveBehavior()
        {
            Beacon("战斗结束, 关闭监听");
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
                Beacon("端口 " + Port + " 监听中");
            }
            catch (Exception e)
            {
                // Port taken (stale battle scene still shutting down) - stay silent.
                Beacon("端口 " + Port + " 打开失败: " + e.Message);
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

        /// <summary>玩家所在位置 (操控角色; 没有则用主将; 再没有则原点)。</summary>
        private static TaleWorlds.Library.Vec2 PlayerPos()
        {
            var me = Mission.Current.MainAgent;
            if (me != null)
                return me.Position.AsVec2;
            return Mission.Current.PlayerTeam.GeneralAgent?.Position.AsVec2
                   ?? TaleWorlds.Library.Vec2.Zero;
        }

        private string Info()
        {
            if (!InBattle())
                return "err no_battle";
            var pos = PlayerPos();
            var sb = new StringBuilder("ok");
            foreach (var f in EnemyFormations())
            {
                sb.Append(' ').Append(f.FormationIndex)
                  .Append(':').Append(f.CountOfUnits)
                  .Append(':').Append((int)f.CachedAveragePosition.Distance(pos));
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

            var enemies = EnemyFormations();
            if (enemies.Count == 0)
                return "err no_enemies";

            // 2. resolve target mode
            //    "player": 集火离玩家最近的那支(混战里"打这只/打他"的本能, 多半
            //              指玩家眼前的敌军) —— 所有被下令编队都打同一支。
            //    <兵种>  : 定向按敌方兵种(骑兵专打敌弓箭手) —— 每支各打自己最近的
            //              该类敌军, 多队自然铺开。
            var byClass = false;
            FormationClass tc = FormationClass.Infantry;
            Formation fixedTarget = null;
            if (targetName == "player")
            {
                var ppos = PlayerPos();
                var bd = float.MaxValue;
                foreach (var e in enemies)
                {
                    var d = e.CachedAveragePosition.Distance(ppos);
                    if (d < bd) { bd = d; fixedTarget = e; }
                }
                if (fixedTarget == null)
                    return "err no_target";
            }
            else
            {
                if (!TryClass(targetName, out tc))
                    return "err bad_target";
                byClass = true;
            }

            // 3. each commanded formation charges its own best-matching target.
            //    IMPORTANT: use the exact native PLAYER order path
            //    (OrderController.SetOrderWithFormation(Charge, target) =
            //     MovementOrderCharge + SetTargetFormation) — decompiled from
            //    OrderController.cs. MovementOrderChargeToTarget is the AI-behavior
            //    path and does NOT reproduce the hover-targeted charge players get.
            //    Going through PlayerOrderController also fires order events, syncs
            //    the order UI and plays the charge voice line.
            var oc = player.PlayerOrderController;
            var backup = new List<Formation>();
            foreach (Formation f in oc.SelectedFormations)
                backup.Add(f);

            var done = 0;
            var lastDesc = "";
            // 位置一律用 CachedAveragePosition(编队实际士兵均值, RTSCamera 同款),
            // 不用 CurrentPosition(空编队/纵队会退回下令点, 不准)。
            foreach (var g in groups)
            {
                Formation best = fixedTarget;   // player 模式: 固定同一目标(集火)
                if (best == null)               // 按兵种模式: 各打各自最近的该类敌军
                {
                    var bestD = float.MaxValue;
                    foreach (var e in enemies)
                    {
                        if (byClass && e.FormationIndex != tc)
                            continue;
                        var d = g.CachedAveragePosition.Distance(e.CachedAveragePosition);
                        if (d < bestD) { bestD = d; best = e; }
                    }
                }
                if (best == null)
                    continue;
                oc.ClearSelectedFormations();
                oc.SelectFormation(g);
                oc.SetOrderWithFormation(OrderType.Charge, best);
                done++;
                lastDesc = best.FormationIndex + ":" + best.CountOfUnits;
            }

            // put the player's own UI selection back the way it was
            oc.ClearSelectedFormations();
            foreach (var f in backup)
                oc.SelectFormation(f);

            return done == 0
                ? "err target_not_found"
                : "ok attacked=" + done + " target=" + lastDesc;
        }
    }
}
