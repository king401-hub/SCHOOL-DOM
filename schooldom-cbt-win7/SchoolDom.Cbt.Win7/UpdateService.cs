using System;
using System.IO;
using System.Net;
using System.Text;

namespace SchoolDom.Cbt.Win7
{
    public class UpdateInfo
    {
        public string LatestVersion { get; set; }
        public string ReleaseNotes  { get; set; }
        public string ReleaseDate   { get; set; }
        public string DownloadUrl   { get; set; }
        public long?  FileSizeBytes { get; set; }
        public bool   IsMandatory   { get; set; }

        public bool IsNewerThan(string currentVersion)
        {
            try
            {
                return new Version(Normalize(LatestVersion)) > new Version(Normalize(currentVersion));
            }
            catch
            {
                return string.Compare(LatestVersion ?? "", currentVersion ?? "",
                    StringComparison.OrdinalIgnoreCase) > 0;
            }
        }

        private static string Normalize(string v)
        {
            var parts = ((v ?? "0.0.0").TrimStart('v', 'V').Trim()).Split('.');
            var major = parts.Length > 0 ? parts[0] : "0";
            var minor = parts.Length > 1 ? parts[1] : "0";
            var patch = parts.Length > 2 ? parts[2] : "0";
            return major + "." + minor + "." + patch;
        }
    }

    public static class UpdateService
    {
        private const int CheckTimeoutMs    = 10000;  // 10 s — fail fast if no internet
        private const int DownloadTimeoutMs = 300000; // 5 min

        private static string SnoozeFilePath
        {
            get
            {
                return Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "SchoolDomAdminSync", "skip_update_until.txt");
            }
        }

        public static bool IsUpdateSnoozed()
        {
            try
            {
                var path = SnoozeFilePath;
                if (!File.Exists(path)) return false;
                DateTime until;
                return DateTime.TryParse(File.ReadAllText(path).Trim(), out until)
                    && DateTime.UtcNow < until;
            }
            catch { return false; }
        }

        public static void SnoozeUpdate()
        {
            try
            {
                var path = SnoozeFilePath;
                var dir  = Path.GetDirectoryName(path);
                if (!string.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);
                File.WriteAllText(path, DateTime.UtcNow.AddHours(24).ToString("o"));
            }
            catch { /* non-critical */ }
        }

        public static UpdateInfo CheckForUpdate(string cloudUrl)
        {
            var url = (cloudUrl ?? "https://schooldom.academy").TrimEnd('/') + "/api/exams/cbt/version/";
            var req = (HttpWebRequest)WebRequest.Create(url);
            req.Method          = "GET";
            req.Timeout         = CheckTimeoutMs;
            req.ReadWriteTimeout = CheckTimeoutMs;
            req.UserAgent       = "SchoolDom-CBT-Win7";
            req.Accept          = "application/json";

            using (var resp   = (HttpWebResponse)req.GetResponse())
            using (var stream = resp.GetResponseStream())
            using (var reader = new StreamReader(stream ?? Stream.Null, Encoding.UTF8))
            {
                var data          = JsonUtil.DeserializeObject(reader.ReadToEnd());
                var latestVersion = JsonUtil.Text(data.ContainsKey("version") ? data["version"] : null);
                if (string.IsNullOrWhiteSpace(latestVersion)) return null;

                var info = new UpdateInfo
                {
                    LatestVersion = latestVersion,
                    ReleaseNotes  = JsonUtil.Text(data.ContainsKey("release_notes") ? data["release_notes"] : null),
                    ReleaseDate   = JsonUtil.Text(data.ContainsKey("release_date")   ? data["release_date"]   : null),
                    DownloadUrl   = JsonUtil.Text(data.ContainsKey("download_url")   ? data["download_url"]   : null),
                    IsMandatory   = data.ContainsKey("is_mandatory") && Convert.ToBoolean(data["is_mandatory"]),
                };

                if (data.ContainsKey("file_size_bytes") && data["file_size_bytes"] != null)
                {
                    long size;
                    if (long.TryParse(Convert.ToString(data["file_size_bytes"]), out size) && size > 0)
                        info.FileSizeBytes = size;
                }
                return info;
            }
        }

        public static void DownloadInstaller(string url, string destPath, Action<int> onProgress)
        {
            var req = (HttpWebRequest)WebRequest.Create(url);
            req.Method           = "GET";
            req.Timeout          = DownloadTimeoutMs;
            req.ReadWriteTimeout = DownloadTimeoutMs;
            req.UserAgent        = "SchoolDom-CBT-Win7";

            using (var resp           = (HttpWebResponse)req.GetResponse())
            using (var responseStream = resp.GetResponseStream())
            {
                var totalBytes = resp.ContentLength;
                var buffer     = new byte[65536];
                long downloaded = 0;
                int lastPct    = -1;

                var dir = Path.GetDirectoryName(destPath);
                if (!string.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);

                using (var file = new FileStream(destPath, FileMode.Create, FileAccess.Write))
                {
                    int read;
                    while ((read = responseStream.Read(buffer, 0, buffer.Length)) > 0)
                    {
                        file.Write(buffer, 0, read);
                        downloaded += read;
                        if (totalBytes > 0 && onProgress != null)
                        {
                            var pct = (int)((downloaded * 100L) / totalBytes);
                            if (pct != lastPct) { lastPct = pct; onProgress(pct); }
                        }
                    }
                }
                if (onProgress != null) onProgress(100);
            }
        }
    }
}
