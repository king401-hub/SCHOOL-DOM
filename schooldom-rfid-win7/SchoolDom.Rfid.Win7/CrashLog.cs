using System;
using System.IO;

namespace SchoolDom.Rfid.Win7
{
    // Writes to %TEMP%\SchoolDomRfidWin7\crash.log. Exists because this app had no
    // global exception handler at all until this file was added - any unhandled
    // exception anywhere (background thread or UI thread) silently killed the whole
    // process with no dialog and nothing in the Windows Event Log's Application
    // channel to explain why, which is indistinguishable from "the app randomly
    // stops working" to whoever is standing at the gate when it happens.
    internal static class CrashLog
    {
        private static readonly string LogPath = Path.Combine(
            Path.GetTempPath(), "SchoolDomRfidWin7", "crash.log");

        public static void Write(string context, Exception ex)
        {
            try
            {
                Directory.CreateDirectory(Path.GetDirectoryName(LogPath));
                var line = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + "  [" + context + "]  " +
                           ex.GetType().FullName + ": " + ex.Message + Environment.NewLine +
                           ex.StackTrace + Environment.NewLine + new string('-', 60) + Environment.NewLine;
                File.AppendAllText(LogPath, line);
            }
            catch { /* logging must never itself throw */ }
        }
    }
}
