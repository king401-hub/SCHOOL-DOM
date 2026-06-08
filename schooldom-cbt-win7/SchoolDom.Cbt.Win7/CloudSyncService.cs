using System;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Text;

namespace SchoolDom.Cbt.Win7
{
    public class CloudSyncService
    {
        private readonly LocalStore _store;
        private readonly PackageService _packages;

        public CloudSyncService(LocalStore store, PackageService packages)
        {
            _store = store;
            _packages = packages;
            ServicePointManager.SecurityProtocol = SecurityProtocolType.Tls12;
        }

        public string NormalizeCloudUrl(string value)
        {
            var url = (value ?? "").Trim().TrimEnd('/');
            if (url.Length == 0) url = "https://schooldom.academy";
            if (!url.StartsWith("http://", StringComparison.OrdinalIgnoreCase) &&
                !url.StartsWith("https://", StringComparison.OrdinalIgnoreCase))
            {
                url = "https://" + url;
            }
            return url;
        }

        public string Login(string cloudUrl, string email, string password, string schoolCode)
        {
            var body = new Dictionary<string, object>
            {
                { "email", email ?? "" },
                { "password", password ?? "" },
                { "school_code", schoolCode ?? "" }
            };
            var response = Request("POST", NormalizeCloudUrl(cloudUrl) + "/api/auth/login/", JsonUtil.Serialize(body), "");
            var data = JsonUtil.DeserializeObject(response);
            if (data.ContainsKey("requires_otp") && Convert.ToBoolean(data["requires_otp"]))
            {
                throw new InvalidOperationException("This admin account requires OTP. Sign in on the website and paste the JWT access token into this app.");
            }
            if (!data.ContainsKey("access"))
            {
                throw new InvalidOperationException("Login succeeded but no access token was returned.");
            }
            _store.State.CloudUrl = NormalizeCloudUrl(cloudUrl);
            _store.State.AccessToken = Convert.ToString(data["access"]);
            var school = data.ContainsKey("school") ? data["school"] as Dictionary<string, object> : null;
            if (school != null)
            {
                _store.State.SchoolName = school.ContainsKey("name") ? Convert.ToString(school["name"]) : _store.State.SchoolName;
                _store.State.SchoolCode = school.ContainsKey("school_code") ? Convert.ToString(school["school_code"]) : _store.State.SchoolCode;
            }
            if (data.ContainsKey("school_code") && string.IsNullOrWhiteSpace(_store.State.SchoolCode))
            {
                _store.State.SchoolCode = Convert.ToString(data["school_code"]);
            }
            _store.Save();
            return "Signed in to SchoolDom cloud.";
        }

        public string PullPackage(string fallbackPin)
        {
            RequireToken();
            var json = Request("GET", NormalizeCloudUrl(_store.State.CloudUrl) + "/api/exams/cbt/offline-sync/", "", _store.State.AccessToken);
            var result = _packages.ImportPackageJson(json, fallbackPin);
            _store.State.LastSyncAt = JsonUtil.IsoNow();
            _store.Save();
            return result;
        }

        public string UploadResults()
        {
            RequireToken();
            var json = _packages.ExportResultsJson(markExported: false);
            var response = Request("POST", NormalizeCloudUrl(_store.State.CloudUrl) + "/api/exams/cbt/package/results/import/", json, _store.State.AccessToken);
            var data = JsonUtil.DeserializeObject(response);
            var imported = data.ContainsKey("imported") ? Convert.ToString(data["imported"]) : "0";
            var failed = data.ContainsKey("failed") ? Convert.ToString(data["failed"]) : "0";
            _packages.MarkSubmittedResultsSynced();
            _store.State.LastSyncAt = JsonUtil.IsoNow();
            _store.Save();
            return "Uploaded results. Imported: " + imported + ". Failed: " + failed + ".";
        }

        public void SaveToken(string cloudUrl, string accessToken)
        {
            _store.State.CloudUrl = NormalizeCloudUrl(cloudUrl);
            _store.State.AccessToken = NormalizeAccessToken(accessToken);
            _store.Save();
        }

        private void RequireToken()
        {
            if (string.IsNullOrWhiteSpace(_store.State.AccessToken))
            {
                throw new InvalidOperationException("Add an admin JWT access token or sign in before syncing.");
            }
        }

        private static string NormalizeAccessToken(string token)
        {
            var value = (token ?? "").Trim();
            if (value.StartsWith("Bearer ", StringComparison.OrdinalIgnoreCase)) value = value.Substring(7).Trim();
            return value;
        }

        private static string Request(string method, string url, string body, string accessToken)
        {
            var request = (HttpWebRequest)WebRequest.Create(url);
            request.Method = method;
            request.Timeout = 30000;
            request.ContentType = "application/json";
            request.UserAgent = "SchoolDom-CBT-Win7";
            if (!string.IsNullOrWhiteSpace(accessToken))
            {
                request.Headers["Authorization"] = "Bearer " + NormalizeAccessToken(accessToken);
            }
            if (method == "POST")
            {
                var bytes = Encoding.UTF8.GetBytes(body ?? "{}");
                request.ContentLength = bytes.Length;
                using (var stream = request.GetRequestStream())
                {
                    stream.Write(bytes, 0, bytes.Length);
                }
            }
            try
            {
                using (var response = (HttpWebResponse)request.GetResponse())
                using (var stream = response.GetResponseStream())
                using (var reader = new StreamReader(stream ?? Stream.Null))
                {
                    return reader.ReadToEnd();
                }
            }
            catch (WebException ex)
            {
                var message = ex.Message;
                if (ex.Response != null)
                {
                    using (var stream = ex.Response.GetResponseStream())
                    using (var reader = new StreamReader(stream ?? Stream.Null))
                    {
                        var details = reader.ReadToEnd();
                        if (!string.IsNullOrWhiteSpace(details)) message = details;
                    }
                }
                throw new InvalidOperationException("Cloud request failed: " + message);
            }
        }
    }
}
