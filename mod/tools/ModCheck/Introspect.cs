using System;
using System.IO;
using System.Linq;
using System.Reflection;

namespace ModCheck
{
    /// <summary>Headless run of the launcher's Mods page: build LauncherModsVM
    /// exactly like the real launcher and dump each module's checkbox state.</summary>
    internal static class Introspect
    {
        internal static void Run(string gameBin)
        {
            var asm = Assembly.LoadFrom(Path.Combine(gameBin,
                "TaleWorlds.MountAndBlade.Launcher.Library.dll"));
            var udmT = asm.GetTypes().First(x => x.Name == "UserDataManager");
            var vmT = asm.GetTypes().First(x => x.Name == "LauncherModsVM");

            var udm = Activator.CreateInstance(udmT);
            if ((bool)udmT.GetMethod("HasUserData").Invoke(udm, null))
                udmT.GetMethod("LoadUserData").Invoke(udm, null);
            var vm = Activator.CreateInstance(vmT, udm);
            vmT.GetMethod("Refresh").Invoke(vm, new object[] { false, false }); // 单机页

            var mods = (System.Collections.IEnumerable)vmT.GetProperty("Modules").GetValue(vm);
            foreach (var m in mods)
            {
                var t = m.GetType();
                object G(string n) { var p = t.GetProperty(n); return p == null ? null : p.GetValue(m); }
                string Hint(string n)
                {
                    var h = G(n);
                    if (h == null) return "";
                    var tp = h.GetType().GetProperty("Text") ?? h.GetType().GetProperty("HintText");
                    return tp == null ? "" : (tp.GetValue(h) ?? "").ToString();
                }
                var info = G("Info");
                var id = G("Name") ?? "?";
                Console.WriteLine($"{id,-24} sel={G("IsSelected")} disabled={G("IsDisabled")} " +
                    $"depOk={G("AnyDependencyAvailable")} dangerous={G("IsDangerous")}");
                var dh = Hint("DependencyHint"); var dg = Hint("DangerousHint");
                if (!string.IsNullOrEmpty(dh)) Console.WriteLine($"    依赖提示: {dh}");
                if (!string.IsNullOrEmpty(dg)) Console.WriteLine($"    危险提示: {dg}");
            }
        }
    }
}
