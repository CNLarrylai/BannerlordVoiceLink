using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using TaleWorlds.Core;
using TaleWorlds.Library;
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
    ///   tactic <group|all> <flank|manual> -> "ok" (战术层: flank=交给AI绕后,
    ///                     manual=收回指挥权; 键盘玩家摸不到的 FormationAI 层)
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
            HookPlayerOrders();
        }

        // ---------- 影子驱动 (战术行为不交 AI) ----------
        // 教训(2026-09-02 实测): SetControlledByAI(true) 之后团队 AI 的战术层会
        // 接管这个编队 —— 合并步弓、圆阵套方阵(TacticDefensiveRing)、给骑兵派
        // ProtectFlank, 我挂的行为根本赢不了权重竞争, 玩家还改不回来。
        // 游戏只对 AI 控制的编队跑行为树(FormationAI.TickOccasionally 写死),
        // 所以改成模组自己驱动: 激活钩子反射调一次 + 每半秒替它 TickOccasionally
        // (行为在里面自己下移动令/朝向令)。编队全程留在玩家手里; 玩家对它下任何
        // 指令(F键/语音, 走 OrderController) => 事件里自动停掉驱动。
        private sealed class Driven
        {
            public BehaviorComponent B;
            public string Verb;
            public float Next;
        }

        private readonly Dictionary<Formation, Driven> _driven = new Dictionary<Formation, Driven>();
        private static readonly MethodInfo _activateAux = typeof(BehaviorComponent).GetMethod(
            "OnBehaviorActivatedAux", BindingFlags.NonPublic | BindingFlags.Instance);
        private OrderController _hookedOc;

        private void HookPlayerOrders()
        {
            try
            {
                var oc = Mission.Current?.PlayerTeam?.PlayerOrderController;
                if (oc == null || _hookedOc == oc) return;
                oc.OnOrderIssued += OnPlayerOrderIssued;
                _hookedOc = oc;
            }
            catch (Exception e) { Beacon("hook orders err " + e.Message); }
        }

        private void OnPlayerOrderIssued(OrderType orderType, MBReadOnlyList<Formation> formations,
                                         OrderController oc, params object[] delegateParams)
        {
            if (_driven.Count == 0 || formations == null) return;
            foreach (var f in formations)
                if (_driven.Remove(f))
                    Beacon("drive stop " + f.FormationIndex + " (player order " + orderType + ")");
        }

        private void Drive(Formation f, BehaviorComponent b, string verb)
        {
            if (f.IsAIControlled)
                f.SetControlledByAI(false);       // 绝不交 AI(见上)
            try
            {
                _activateAux?.Invoke(b, null);   // 行为自己设阵型/射击令并下第一条移动令
            }
            catch (Exception e) { Beacon("drive activate err " + e.Message); }
            _driven[f] = new Driven { B = b, Verb = verb, Next = 0f };
            Beacon("drive " + verb + " " + f.FormationIndex + " units=" + f.CountOfUnits);
        }

        private void StopDriving(Formation f)
        {
            if (_driven.Remove(f))
                Beacon("drive stop " + f.FormationIndex + " (manual)");
        }

        private void DriveTick()
        {
            if (_driven.Count == 0 || Mission.Current == null) return;
            float now = Mission.Current.CurrentTime;
            foreach (var kv in _driven.ToList())
            {
                var f = kv.Key; var d = kv.Value;
                if (f.CountOfUnits == 0 || f.IsAIControlled)   // 没兵了 / 玩家 F6 交了 AI
                {
                    _driven.Remove(f);
                    continue;
                }
                if (now < d.Next) continue;
                d.Next = now + 0.5f;
                try
                {
                    d.B.TickOccasionally();
                    if (d.B.IsCurrentOrderChanged)
                    {
                        f.SetMovementOrder(d.B.CurrentOrder);
                        d.B.IsCurrentOrderChanged = false;
                    }
                }
                catch (Exception e)
                {
                    Beacon("drive tick err " + d.Verb + " " + e.Message);
                    _driven.Remove(f);
                }
            }
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
            _driven.Clear();
            try { if (_hookedOc != null) _hookedOc.OnOrderIssued -= OnPlayerOrderIssued; } catch { }
            _hookedOc = null;
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
            DriveTick();
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
                        ? "err usage: sideorder <group> <left|right> <order> [target]"
                        : DoSideOrder(parts[1], parts[2], parts[3],
                                      parts.Length > 4 ? parts[4] : "-");
                case "formorder":
                    return parts.Length < 3
                        ? "err usage: formorder <slot 1-8> <order> [target]"
                        : DoFormOrder(parts[1], parts[2],
                                      parts.Length > 3 ? parts[3] : "-");
                case "tactic":
                    return parts.Length < 3
                        ? "err usage: tactic <group|all> <flank|manual>"
                        : DoTactic(parts[1], parts[2]);
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

        // ---------- 语言: 跟随语音程序当前语言 ----------
        // 语音程序启动时把 zh/en 写到 %LOCALAPPDATA%\BannerlordVoice\lang.txt
        // (源码/打包两种形态都写这里); 模组每 2 秒最多读一次, 不走协议 —— 服务器
        // 只在战斗中监听, 用协议同步会有"谁先启动"的时序问题, 文件没有。
        private static string _lang = "zh";
        private static DateTime _langRead = DateTime.MinValue;

        private static bool En
        {
            get
            {
                if ((DateTime.UtcNow - _langRead).TotalSeconds >= 2)
                {
                    _langRead = DateTime.UtcNow;
                    try
                    {
                        var p = Path.Combine(
                            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                            "BannerlordVoice", "lang.txt");
                        if (File.Exists(p))
                            _lang = File.ReadAllText(p).Trim().ToLowerInvariant()
                                        .StartsWith("en") ? "en" : "zh";
                    }
                    catch { /* 读不到就沿用上次 */ }
                }
                return _lang == "en";
            }
        }

        private static string T(string zh, string en) { return En ? en : zh; }

        /// <summary>"(12人)" / " (12)"</summary>
        private static string Units(int n)
        {
            return En ? " (" + n + ")" : "(" + n + "人)";
        }

        /// <summary>第N队 / Group N</summary>
        private static string FormLabel(int n)
        {
            return En ? "Group " + n : "第" + CnNums[n - 1] + "队";
        }

        private static string Cn(FormationClass fc)
        {
            if (En)
            {
                switch (fc)
                {
                    case FormationClass.Infantry: return "Infantry";
                    case FormationClass.Ranged: return "Archers";
                    case FormationClass.Cavalry: return "Cavalry";
                    case FormationClass.HorseArcher: return "Horse Archers";
                    default: return fc.ToString();
                }
            }
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
            if (En)
            {
                switch (name)
                {
                    case "infantry": return "Infantry";
                    case "archers": return "Archers";
                    case "cavalry": return "Cavalry";
                    case "horse_archers": return "Horse Archers";
                    case "all": return "All units";
                    default: return name;
                }
            }
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
                    new TaleWorlds.Localization.TextObject(T("【语音】", "[Voice] ") + text));
            }
            catch
            {
                // 横幅 API 变动/失败不影响下令, 还有下面的记录兜底
            }
            try
            {
                TaleWorlds.Library.InformationManager.DisplayMessage(
                    new TaleWorlds.Library.InformationMessage(
                        T("【语音】", "[Voice] ") + text,
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
                if (g.IsAIControlled)
                    StopDriving(g);              // 直接指令打断战术驱动
                    g.SetControlledByAI(false);
                oc.ClearSelectedFormations();
                oc.SelectFormation(g);
                oc.SetOrderWithFormation(OrderType.Charge, best);
                done++;
                lastDesc = best.FormationIndex + ":" + best.CountOfUnits;
                // 按兵种模式各队目标不同, 逐队报; 集火模式统一在循环外报一条
                if (fixedTarget == null)
                    Notify(Cn(g.FormationIndex) + T(" → 进攻敌方", " → attacking enemy ")
                           + Cn(best.FormationIndex) + Units(best.CountOfUnits));
            }
            if (fixedTarget != null && done > 0)
                Notify(CnGroup(groupName) + T(" → 集火最近敌军: ", " → focus nearest enemy: ")
                       + Cn(fixedTarget.FormationIndex) + Units(fixedTarget.CountOfUnits));

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
        // 最近分队的兵种: 光喊"左队/右队"(不带兵种前缀)时默认指它
        private FormationClass _lastSplit = FormationClass.NumberOfAllFormations;

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
            var player = Mission.Current.PlayerTeam;
            var src = player.GetFormation(gc);
            int n0 = (src == null) ? -1 : src.CountOfUnits;
            Beacon("DoSplit " + gc + " src单位=" + n0);
            if (src == null || src.CountOfUnits < 2)
                return "err too_few";       // 1 个兵没法分

            // 找一个空编队槽(0-7)接收新半队。Formation.Split() 走 MasterOrder-
            // Controller.SplitFormation, 被 IsSplittableByAI 门禁挡住(玩家亲自
            // 指挥的编队该值为 false)对玩家无效。改用它内部真正搬兵那步
            // TransferUnitsAux + isPlayerOrder:true 强制绕过 AI 门禁。
            Formation target = null;
            for (int i = 0; i < 8; i++)
            {
                var f = player.GetFormation((FormationClass)i);
                if (f != null && f.CountOfUnits == 0) { target = f; break; }
            }
            if (target == null)
                return "err no_empty_slot";   // 8 个槽全占满, 没处放新队

            int half = src.CountOfUnits / 2;
            try
            {
                src.TransferUnitsAux(target, half, true, false);   // isPlayerOrder=true
            }
            catch (Exception e)
            {
                Beacon("Transfer异常: " + e.Message);
                return "err split_ex";
            }
            Beacon("DoSplit 结果 target槽=" + (int)target.FormationIndex
                   + " target单位=" + target.CountOfUnits
                   + " src现在=" + src.CountOfUnits);
            if (target.CountOfUnits == 0)
                return "err split_failed";

            _splits[gc] = new[] { src, target };   // [0]原队=左, [1]新队=右
            _lastSplit = gc;
            // 新半队落在哪个槽 => 第几队, 告诉玩家(槽号取决于分队顺序, 不显式
            // 说出来玩家没法用"第N队"指挥新队)
            int newNo = (int)target.FormationIndex + 1;
            Notify(En
                ? Cn(gc) + " split in two: Left = original, Right = " + FormLabel(newNo)
                : Cn(gc) + "已分两队：左队=原队, 右队=" + FormLabel(newNo));
            return "ok split=" + gc + " a=" + src.CountOfUnits
                   + " b=" + target.CountOfUnits + " slot=" + newNo;
        }

        private string DoSideOrder(string groupName, string side, string order,
                                   string target)
        {
            if (!InBattle())
                return "err no_battle";
            FormationClass gc;
            if (groupName == "last")        // 光喊"左队/右队" => 最近分的那队
            {
                if (_lastSplit == FormationClass.NumberOfAllFormations)
                    return "err not_split";
                gc = _lastSplit;
            }
            else if (!TryClass(groupName, out gc))
                return "err bad_group";
            Formation[] pair;
            if (!_splits.TryGetValue(gc, out pair)
                || pair[0] == null || pair[1] == null
                || pair[0].CountOfUnits == 0 || pair[1].CountOfUnits == 0)
                return "err not_split";     // 这个兵种还没分队 / 分的队没了

            var pick = (side == "left") ? pair[0] : pair[1];   // 左=原 右=新
            Beacon("DoSideOrder " + gc + " " + side + " tgt=" + target
                   + " -> " + pick.CountOfUnits + "人");
            return IssueToFormation(pick, order,
                Cn(gc) + (side == "left" ? T("左队", " Left") : T("右队", " Right")), target);
        }

        private static readonly string[] CnNums =
            { "一", "二", "三", "四", "五", "六", "七", "八" };

        private string DoFormOrder(string slotStr, string order, string target)
        {
            if (!InBattle())
                return "err no_battle";
            int n;
            if (!int.TryParse(slotStr, out n) || n < 1 || n > 8)
                return "err bad_slot";
            var pick = Mission.Current.PlayerTeam.GetFormation((FormationClass)(n - 1));
            Beacon("DoFormOrder 第" + n + "队 -> "
                   + (pick == null ? "null" : pick.CountOfUnits + "人"));
            if (pick == null || pick.CountOfUnits == 0)
                return "err empty_formation";   // 这个槽位没兵(还没分队/无此队)
            return IssueToFormation(pick, order, FormLabel(n), target);
        }

        /// <summary>选中某编队 -> 下派遣令 -> 恢复原选择 -> 播报。左右/第N队共用。
        /// target 非空且 order=charge 时走"定向进攻"(冲最近的该类敌军)。</summary>
        private string IssueToFormation(Formation pick, string order, string label,
                                        string target)
        {
            StopDriving(pick);                   // 直接指令打断战术驱动(绕后等)
            if (pick.IsAIControlled)
                pick.SetControlledByAI(false);
            var oc = Mission.Current.PlayerTeam.PlayerOrderController;
            var backup = new List<Formation>(oc.SelectedFormations);

            // 定向进攻: "骑兵左队进攻弓箭手" => 该半队冲最近的敌方弓箭手(带目标),
            // 而非简单冲锋最近的任意敌军。状态播报也带上打的是谁。
            FormationClass tc;
            if (order == "charge" && !string.IsNullOrEmpty(target) && target != "-"
                && TryClass(target, out tc))
            {
                Formation enemy = null;
                float bd = float.MaxValue;
                foreach (var e in EnemyFormations())
                {
                    if (e.FormationIndex != tc) continue;
                    var d = pick.CachedAveragePosition.Distance(e.CachedAveragePosition);
                    if (d < bd) { bd = d; enemy = e; }
                }
                if (enemy != null)
                {
                    oc.ClearSelectedFormations();
                    oc.SelectFormation(pick);
                    oc.SetOrderWithFormation(OrderType.Charge, enemy);
                    oc.ClearSelectedFormations();
                    foreach (var f in backup) oc.SelectFormation(f);
                    Notify(label + T(" → 进攻敌方", " → attacking enemy ") + Cn(tc)
                           + Units(enemy.CountOfUnits));
                    return "ok target=" + tc + " units=" + pick.CountOfUnits;
                }
                // 场上没有该类敌军 => 退化为简单冲锋(往下走)
            }

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
            oc.ClearSelectedFormations();
            oc.SelectFormation(pick);
            oc.SetOrder(ot);
            oc.ClearSelectedFormations();
            foreach (var f in backup)
                oc.SelectFormation(f);
            Notify(label + " → " + CnOrder(order) + Units(pick.CountOfUnits));
            return "ok units=" + pick.CountOfUnits;
        }

        // ---------- 战术层 (FormationAI, 键盘玩家摸不到的那层) ----------

        private string DoTactic(string groupName, string verb)
        {
            if (!InBattle())
                return "err no_battle";
            var player = Mission.Current.PlayerTeam;
            var targets = new List<Formation>();
            if (groupName == "all")
            {
                foreach (var f in OwnNonEmpty())
                    targets.Add(f);
            }
            else
            {
                FormationClass gc;
                if (!TryClass(groupName, out gc))
                    return "err bad_group";
                var f = player.GetFormation(gc);
                if (f == null || f.CountOfUnits == 0)
                    return "err group_empty";
                targets.Add(f);
            }

            var label = CnGroup(groupName);   // "all" 已在表里(全军 / All units)
            switch (verb)
            {
                case "flank":
                    foreach (var f in targets)
                        Drive(f, new BehaviorFlank(f), verb);
                    Notify(label + T(" → 绕后包抄(自动执行, 下任何指令即停)",
                                     " → flanking (auto; any direct order stops it)"));
                    return "ok tactic=flank n=" + targets.Count;
                case "manual":
                    foreach (var f in targets)
                    {
                        StopDriving(f);
                        f.SetControlledByAI(false);
                        Beacon("tactic manual " + f.FormationIndex);
                    }
                    Notify(label + T(" → 已收回指挥权, 听你号令", " → back under your command"));
                    return "ok tactic=manual n=" + targets.Count;
                // ---- 第二批(2026-09): 与 flank 同一机制, 只是换行为类 ----
                case "highground":
                    foreach (var f in targets)
                    {
                        var hg = new BehaviorHoldHighGround(f);
                        // 非远程编队占高地时, 告诉它己方最大的弓箭手编队在哪, 它会按射程留距离
                        if (!f.QuerySystem.IsRangedFormation)
                            hg.RangedAllyFormation = OwnNonEmpty()
                                .Where(x => x != f && x.QuerySystem.IsRangedFormation)
                                .OrderByDescending(x => x.CountOfUnits).FirstOrDefault();
                        Drive(f, hg, verb);
                    }
                    Notify(label + T(" → 占据高地(自动执行, 下任何指令即停)",
                                     " → holding the high ground (auto; any direct order stops it)"));
                    return "ok tactic=highground n=" + targets.Count;
                case "skirmish":
                    foreach (var f in targets)
                    {
                        // 按兵种挑游击实现: 骑射专用 / 步弓散阵拉距离 / 骑兵机动游击
                        BehaviorComponent b;
                        switch (f.FormationIndex)
                        {
                            case FormationClass.HorseArcher: b = new BehaviorHorseArcherSkirmish(f); break;
                            case FormationClass.Cavalry: b = new BehaviorMountedSkirmish(f); break;
                            default: b = new BehaviorSkirmish(f); break;
                        }
                        Drive(f, b, verb);
                    }
                    Notify(label + T(" → 游击骚扰(自动执行, 下任何指令即停)",
                                     " → skirmishing (auto; any direct order stops it)"));
                    return "ok tactic=skirmish n=" + targets.Count;
                case "cautious":
                    foreach (var f in targets)
                        Drive(f, new BehaviorCautiousAdvance(f), verb);
                    Notify(label + T(" → 稳步推进(盾墙/贴弓箭手射程, 下任何指令即停)",
                                     " → advancing carefully (auto; any direct order stops it)"));
                    return "ok tactic=cautious n=" + targets.Count;
                case "protect":
                    foreach (var f in targets)
                        Drive(f, new BehaviorDefensiveRing(f), verb);
                    Notify(label + T(" → 护住弓箭手(结圆阵护弓, 下任何指令即停)",
                                     " → protecting the archers (auto; any direct order stops it)"));
                    return "ok tactic=protect n=" + targets.Count;
                default:
                    return "err bad_tactic";
            }
        }

        private static string CnOrder(string order)
        {
            if (En)
            {
                switch (order)
                {
                    case "charge": return "Charge";
                    case "advance": return "Advance";
                    case "follow": return "Follow me";
                    case "halt": return "Hold position";
                    case "fallback": return "Fall back";
                    case "retreat": return "Retreat";
                    default: return order;
                }
            }
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
