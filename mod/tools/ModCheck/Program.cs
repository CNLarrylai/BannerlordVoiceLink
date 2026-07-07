using System;
using System.IO;
using System.Linq;
using System.Reflection;

namespace ModCheck
{
    /// <summary>
    /// Loads the game's own TaleWorlds.ModuleManager.dll and asks IT to parse
    /// our module + a known-good reference module, then dumps what the launcher
    /// actually sees. Run: ModCheck.exe <gameDir> <moduleId> <referenceModuleId>
    /// </summary>
    internal static class Program
    {
        private static string _gameBin;

        private static int Main(string[] args)
        {
            var gameDir = args.Length > 0 ? args[0]
                : @"C:\SteamLibraryforstream\steamapps\common\Mount & Blade II Bannerlord";
            var modId = args.Length > 1 ? args[1] : "BannerlordVoiceLink";
            var refId = args.Length > 2 ? args[2] : "FastMode";
            _gameBin = Path.Combine(gameDir, "bin", "Win64_Shipping_Client");

            AppDomain.CurrentDomain.AssemblyResolve += (s, e) =>
            {
                var name = new AssemblyName(e.Name).Name + ".dll";
                var p = Path.Combine(_gameBin, name);
                return File.Exists(p) ? Assembly.LoadFrom(p) : null;
            };

            var mm = Assembly.LoadFrom(Path.Combine(_gameBin, "TaleWorlds.ModuleManager.dll"));
            var miType = mm.GetTypes().FirstOrDefault(t => t.Name == "ModuleInfo");
            if (miType == null)
            {
                Console.WriteLine("!! ModuleInfo type not found");
                return 2;
            }
            Console.WriteLine("== ModuleInfo load methods ==");
            foreach (var m in miType.GetMethods(BindingFlags.Public | BindingFlags.Instance | BindingFlags.Static)
                     .Where(m => m.Name.IndexOf("Load", StringComparison.OrdinalIgnoreCase) >= 0))
                Console.WriteLine("  " + m.Name + "(" +
                    string.Join(", ", m.GetParameters().Select(p => p.ParameterType.Name + " " + p.Name)) + ")");

            if (args.Length > 3 && args[3] == "introspect") { Introspect.Run(_gameBin); return 0; }
            var a = Dump(gameDir, miType, modId);
            var b = Dump(gameDir, miType, refId);
            if (a == null || b == null)
                return 3;

            Console.WriteLine("\n== DIFF (launcher-visible fields, mod vs reference) ==");
            foreach (var prop in miType.GetProperties(BindingFlags.Public | BindingFlags.Instance))
            {
                object va = SafeGet(prop, a), vb = SafeGet(prop, b);
                var sa = Render(va);
                var sb = Render(vb);
                if (sa != sb)
                    Console.WriteLine($"  {prop.Name}: mine={sa}  ref={sb}");
            }
            return 0;
        }

        private static object Dump(string gameDir, Type miType, string moduleId)
        {
            var dir = Path.Combine(gameDir, "Modules", moduleId);
            Console.WriteLine($"\n== {moduleId} ({dir}) ==");
            if (!Directory.Exists(dir))
            {
                Console.WriteLine("  !! module dir missing");
                return null;
            }
            var mi = Activator.CreateInstance(miType);
            // Try the loader signatures across game versions, most specific first.
            var attempts = new[]
            {
                new object[] { moduleId, false, dir },  // LoadWithFullPath(id, isOfficial?, path)?
                new object[] { dir },                   // LoadWithFullPath(path)
                new object[] { moduleId, dir },         // (id, path)
            };
            Exception last = null;
            var loaded = false;
            foreach (var m in miType.GetMethods(BindingFlags.Public | BindingFlags.Instance)
                     .Where(m => m.Name.IndexOf("Load", StringComparison.OrdinalIgnoreCase) >= 0))
            {
                foreach (var args in attempts)
                {
                    var ps = m.GetParameters();
                    if (ps.Length != args.Length)
                        continue;
                    var ok = true;
                    for (var i = 0; i < ps.Length; i++)
                        if (!ps[i].ParameterType.IsInstanceOfType(args[i]))
                            ok = false;
                    if (!ok)
                        continue;
                    try
                    {
                        m.Invoke(mi, args);
                        Console.WriteLine($"  loaded via {m.Name}/{ps.Length}");
                        loaded = true;
                        break;
                    }
                    catch (TargetInvocationException e)
                    {
                        last = e.InnerException ?? e;
                    }
                }
                if (loaded)
                    break;
            }
            if (!loaded)
            {
                Console.WriteLine("  !! PARSE FAILED: " + (last == null ? "no matching loader" : last.ToString()));
                return null;
            }
            foreach (var prop in miType.GetProperties(BindingFlags.Public | BindingFlags.Instance))
                Console.WriteLine($"  {prop.Name} = {Render(SafeGet(prop, mi))}");
            return mi;
        }

        private static object SafeGet(PropertyInfo p, object o)
        {
            try { return p.GetValue(o); }
            catch (Exception e) { return "<threw " + e.GetType().Name + ">"; }
        }

        private static string Render(object v)
        {
            if (v == null) return "null";
            if (v is System.Collections.IEnumerable en && !(v is string))
            {
                var items = en.Cast<object>().Select(x => x?.ToString() ?? "null");
                return "[" + string.Join("; ", items) + "]";
            }
            return v.ToString();
        }
    }
}
