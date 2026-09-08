using System;
using System.IO;
using System.Security.Cryptography;
using System.Text;

namespace SchoolDom.StudentCbt.Win7
{
    public class LocalSettingsData
    {
        public string SettingsPinHash { get; set; }
        public string LastLanServerUrl { get; set; }
    }

    // Persists the admin-only Settings PIN and the last-known LAN server address to this
    // PC's AppData - never synced anywhere, never sent to a server. The threat model is a
    // student sitting at this specific exam-hall PC, not a determined attacker with disk
    // access, so an unsalted SHA-256 hash is enough (no need for DPAPI/Django-grade hashing).
    public static class LocalSettingsStore
    {
        private static readonly string SettingsPath = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            "SchoolDom", "StudentCbt", "settings.json");

        public static LocalSettingsData Load()
        {
            try
            {
                if (!File.Exists(SettingsPath)) return new LocalSettingsData();
                var json = File.ReadAllText(SettingsPath);
                var raw = JsonUtil.Object(json);
                return new LocalSettingsData
                {
                    SettingsPinHash = raw.ContainsKey("SettingsPinHash") ? JsonUtil.Text(raw["SettingsPinHash"]) : null,
                    LastLanServerUrl = raw.ContainsKey("LastLanServerUrl") ? JsonUtil.Text(raw["LastLanServerUrl"]) : null
                };
            }
            catch
            {
                return new LocalSettingsData();
            }
        }

        public static void Save(LocalSettingsData data)
        {
            try
            {
                Directory.CreateDirectory(Path.GetDirectoryName(SettingsPath));
                var json = JsonUtil.Serialize(new System.Collections.Generic.Dictionary<string, object>
                {
                    { "SettingsPinHash", data.SettingsPinHash ?? "" },
                    { "LastLanServerUrl", data.LastLanServerUrl ?? "" }
                });
                File.WriteAllText(SettingsPath, json);
            }
            catch
            {
                // Best-effort - a failed save just means the next launch re-runs discovery/setup.
            }
        }

        public static string HashPin(string pin)
        {
            using (var sha = SHA256.Create())
            {
                var bytes = sha.ComputeHash(Encoding.UTF8.GetBytes(pin ?? ""));
                return BitConverter.ToString(bytes).Replace("-", "").ToLowerInvariant();
            }
        }
    }
}
