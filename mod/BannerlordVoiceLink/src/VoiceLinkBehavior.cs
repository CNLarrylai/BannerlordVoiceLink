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
    /// Protocol: one UTF-8 line per request, one line per reply.
    ///   ping                      -> "ok battle=1|0"
    ///   info                      -> "ok Ranged:80:142 Cavalry:40:200 ..." (enemy formations: class:units:dist)
    ///   attack <group> <target>   -> "ok attacked=N target=Ranged:80:142" or "err <reason>"
    ///   split <group>             -> "ok split=Cavalry a=20 b=20" (原生一分为二)
    ///   sideorder <group> <left|right> <order> -> "ok" (左=原队/右=新队,
    ///                     order=charge/advance/follow/halt/fallback/retreat)
    ///   formorder <slot 1-8> <order> -> "ok" (按编队槽位号"第N队"指挥)
    ///   notify <中文文本>          -> "ok"  (顶部快讯横幅播报普通按键指令)
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
                    using (var reader = new StreamReader(stream, new UTF8Encoding(false)))
                    // UTF8Encoding(false): 不带 BOM —— 带 BOM 会污染首条回复,
                    // Python 侧 "ok"/"err" 前缀判断会失灵
                    using (var writer = new StreamWriter(stream, new UTF8Encoding(false)) { AutoFlush = true })
                    {
                        var line = reader.ReadLine();
                        if (line == null)
                            continue;
                        // (协议已转 UTF-8: notify 带中文; ASCII 命令不受影响)
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
            // notify 的正文是自由中文(可含空格), 不走按空格分词
            if (line.StartsWith("notify ", StringComparison.Ordinal))
            {
                var text = line.Substring(7).Trim();
                if (text.Length == 0)
                    return "err empty_text";
                Notify(text);
                return "ok";
            }
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
                case "split":
                    return parts.Length < 2
                        ? "err usage: split <group>"
                        : DoSplit(parts[1]);
                case "sideorder":
                    return parts.Length < 4
                        ? "err usage: sideorder <group> <left|right> <order>"
                        : DoSideOrder(parts[1], parts[2], parts[3]);
                case "formorder":
                    return parts.Length < 3
                        ? "err usage: formorder <slot 1-8> <order>"
                        : DoFormOrder(parts[1], parts[2]);
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

        // ---------- 游戏内通知 ----------
        // 模组下的定向指令不走游戏原生的下令 UI 反馈, 玩家看不到"谁在打谁";
        // 用战斗记录区(左下角)的金色消息把指令说清楚。

        private static string Cn(FormationClass fc)
        {
            switch (fc)
            {
                case FormationClass.Infantry: return "步兵";
                case FormationClass.Ranged: return "弓箭手";
                case FormationClass.Cavalry: return "骑兵";
                case FormationClass.HorseArcher: return "骑射";
                default: return fc.ToString();
            }
        }

        private static string CnGroup(string name)
        {
            switch (name)
            {
                case "infantry": return "步兵";
                case "archers": return "弓箭手";
                case "cavalry": return "骑兵";
                case "horse_archers": return "骑射";
                case "all": return "全军";
                default: return name;
            }
        }

        private static void Notify(string text)
        {
            // 双通道: 顶部快讯横幅(敌军溃逃同款位置, 大字显眼, 观众一眼看到)
            //        + 左下角战斗记录(留痕可回翻, 横幅淡出后还查得到)。
            try
            {
                MBInformationManager.AddQuickInformation(
                    new TaleWorlds.Localization.TextObject("【语音】" + text));
            }
            catch
            {
                // 横幅 API 变动/失败不影响下令, 还有下面的记录兜底
            }
            try
            {
                TaleWorlds.Library.InformationManager.DisplayMessage(
                    new TaleWorlds.Library.InformationMessage(
                        "【语音】" + text,
                        TaleWorlds.Library.Color.FromUint(0xFFD4AF37)));   // 金色
            }
            catch
            {
                // 通知失败绝不影响下令
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
                // 按兵种模式各队目标不同, 逐队报; 集火模式统一在循环外报一条
                if (fixedTarget == null)
                    Notify(Cn(g.FormationIndex) + " → 进攻敌方" + Cn(best.FormationIndex)
                           + "(" + best.CountOfUnits + "人)");
            }
            if (fixedTarget != null && done > 0)
                Notify(CnGroup(groupName) + " → 集火最近敌军: "
                       + Cn(fixedTarget.FormationIndex)
                       + "(" + fixedTarget.CountOfUnits + "人)");

            // put the player's own UI selection back the way it was
            oc.ClearSelectedFormations();
            foreach (var f in backup)
                oc.SelectFormation(f);

            return done == 0
                ? "err target_not_found"
                : "ok attacked=" + done + " target=" + lastDesc;
        }

        // ---------- 分队 ----------
        // 按兵种记录每次分队的两半: [0]=原队(左队), [1]=新分出的(右队)。
        // 左右用固定身份, 不用实时位置 —— 队伍跑起来位置会乱, 但"原队/新队"
        // 永不变, 也对上玩家"原队摆左、新队摆右"的习惯记忆。各兵种独立一套,
        // 骑兵分左右 与 弓箭手分左右 互不干扰(靠兵种前缀区分)。
        private readonly Dictionary<FormationClass, Formation[]> _splits =
            new Dictionary<FormationClass, Formation[]>();

        private List<Formation> OwnNonEmpty()
        {
            var res = new List<Formation>();
            var player = Mission.Current.PlayerTeam;
            foreach (Formation f in player.FormationsIncludingEmpty)
                if (f != null && f.CountOfUnits > 0)
                    res.Add(f);
            return res;
        }

        private string DoSplit(string groupName)
        {
            if (!InBattle())
                return "err no_battle";
            FormationClass gc;
            if (!TryClass(groupName, out gc))
                return "err bad_group";
            var src = Mission.Current.PlayerTeam.GetFormation(gc);
            int n0 = (src == null) ? -1 : src.CountOfUnits;
            Beacon("DoSplit " + gc + " src单位=" + n0);
            if (src == null || src.CountOfUnits < 2)
                return "err too_few";       // 1 个兵没法分

            // 找新分出的编队: 优先用 Split 返回值(那才是权威结果), 前后差集兜底。
            // 不要求新队"分完瞬间就有兵" —— 引擎可能下一 tick 才把兵搬过去,
            // 存下引用即可, sideorder/formorder 下令时会重新看 CountOfUnits。
            var before = new HashSet<Formation>(OwnNonEmpty());
            IEnumerable<Formation> result = null;
            try { result = src.Split(2); }
            catch (Exception e) { Beacon("Split异常: " + e.Message); return "err split_ex"; }

            Formation other = null;
            if (result != null)
                foreach (var f in result)
                    if (f != null && f != src) { other = f; break; }
            if (other == null)              // 返回值没给, 退回前后差集
                foreach (var f in Mission.Current.PlayerTeam.FormationsIncludingEmpty)
                    if (f != null && f != src && !before.Contains(f)
                        && f.CountOfUnits > 0) { other = f; break; }

            Beacon("DoSplit 结果 other="
                   + (other == null ? "null" : other.FormationIndex + ":" + other.CountOfUnits)
                   + " src现在=" + src.CountOfUnits);
            if (other == null)
                return "err split_failed";

            _splits[gc] = new[] { src, other };   // [0]原队=左, [1]新队=右
            Notify(Cn(gc) + " 已分为两队：左队=原队 右队=新队");
            return "ok split=" + gc + " a=" + src.CountOfUnits
                   + " b=" + other.CountOfUnits;
        }

        private string DoSideOrder(string groupName, string side, string order)
        {
            if (!InBattle())
                return "err no_battle";
            FormationClass gc;
            if (!TryClass(groupName, out gc))
                return "err bad_group";
            Formation[] pair;
            if (!_splits.TryGetValue(gc, out pair)
                || pair[0] == null || pair[1] == null
                || pair[0].CountOfUnits == 0 || pair[1].CountOfUnits == 0)
                return "err not_split";     // 这个兵种还没分队 / 分的队没了

            var pick = (side == "left") ? pair[0] : pair[1];   // 左=原 右=新
            return IssueToFormation(pick, order,
                Cn(gc) + (side == "left" ? "左队" : "右队"));
        }

        private static readonly string[] CnNums =
            { "一", "二", "三", "四", "五", "六", "七", "八" };

        private string DoFormOrder(string slotStr, string order)
        {
            if (!InBattle())
                return "err no_battle";
            int n;
            if (!int.TryParse(slotStr, out n) || n < 1 || n > 8)
                return "err bad_slot";
            var pick = Mission.Current.PlayerTeam.GetFormation((FormationClass)(n - 1));
            if (pick == null || pick.CountOfUnits == 0)
                return "err empty_formation";   // 这个槽位没兵(还没分队/无此队)
            return IssueToFormation(pick, order, "第" + CnNums[n - 1] + "队");
        }

        /// <summary>选中某编队 -> 下派遣令 -> 恢复原选择 -> 播报。左右/第N队共用。</summary>
        private string IssueToFormation(Formation pick, string order, string label)
        {
            OrderType ot;
            switch (order)
            {
                case "charge": ot = OrderType.Charge; break;
                case "advance": ot = OrderType.Advance; break;
                case "follow": ot = OrderType.FollowMe; break;
                case "halt": ot = OrderType.StandYourGround; break;
                case "fallback": ot = OrderType.FallBack; break;
                case "retreat": ot = OrderType.Retreat; break;
                default: return "err bad_order";
            }
            var oc = Mission.Current.PlayerTeam.PlayerOrderController;
            var backup = new List<Formation>(oc.SelectedFormations);
            oc.ClearSelectedFormations();
            oc.SelectFormation(pick);
            oc.SetOrder(ot);
            oc.ClearSelectedFormations();
            foreach (var f in backup)
                oc.SelectFormation(f);
            Notify(label + " → " + CnOrder(order) + "(" + pick.CountOfUnits + "人)");
            return "ok units=" + pick.CountOfUnits;
        }

        private static string CnOrder(string order)
        {
            switch (order)
            {
                case "charge": return "冲锋";
                case "advance": return "前进";
                case "follow": return "跟随";
                case "halt": return "原地待命";
                case "fallback": return "后退";
                case "retreat": return "撤退";
                default: return order;
            }
        }
    }
}
