using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace SchoolDom.Cbt.Win7
{
    public class CloudAuthExpiredException : InvalidOperationException
    {
        public CloudAuthExpiredException(string message) : base(message) { }
    }

    public class CloudSyncService
    {
        private readonly LocalStore _store;
        private readonly PackageService _packages;

        // How often the background loop retries any still-unsynced submitted results.
        // Short enough that a transient network blip (the whole reason this needs a
        // retry loop) clears within a minute; cheap enough to run forever, since an
        // empty-pending tick costs nothing but a local list scan.
        private const int ResultSyncIntervalMs = 60000;
        private System.Threading.Timer _resultSyncTimer;
        private volatile bool _resultSyncInFlight;

        public CloudSyncService(LocalStore store, PackageService packages)
        {
            _store = store;
            _packages = packages;
            // Tls12 (3072) is not a named member in the .NET 4.0 enum — use numeric cast.
            // The admin app connects to HTTPS cloud endpoints so we want TLS 1.2 when available.
            try { ServicePointManager.SecurityProtocol = (SecurityProtocolType)3072; }  // TLS 1.2
            catch { ServicePointManager.SecurityProtocol = SecurityProtocolType.Tls; }
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
            if (!data.ContainsKey("access"))
            {
                throw new InvalidOperationException("Login succeeded but no access token was returned.");
            }
            _store.State.CloudUrl = NormalizeCloudUrl(cloudUrl);
            _store.State.AccessToken = Convert.ToString(data["access"]);
            _store.State.RefreshToken = data.ContainsKey("refresh") ? Convert.ToString(data["refresh"]) : null;
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

        /// <summary>
        /// Activates a CBT license key for this school - the same key entry point the
        /// React admin console offers ("Enter License Key"), reused here so the offline
        /// Win7 app can unlock CBT without needing the website at all once activated.
        /// A valid key immediately unlocks CBT; the server is the sole authority on
        /// whether a key is valid, unexpired, and belongs to this school.
        /// </summary>
        public string ActivateLicense(string key)
        {
            RequireToken();
            var body = new Dictionary<string, object> { { "key", (key ?? "").Trim() } };
            var response = RequestAuthenticated("POST", NormalizeCloudUrl(_store.State.CloudUrl) + "/api/app/license/activate/", JsonUtil.Serialize(body));
            var data = JsonUtil.DeserializeObject(response);
            if (!data.ContainsKey("success") || !Convert.ToBoolean(data["success"]))
            {
                throw new InvalidOperationException(data.ContainsKey("message") ? Convert.ToString(data["message"]) : "Could not activate this license key.");
            }
            var license = data.ContainsKey("license") ? data["license"] as Dictionary<string, object> : null;
            _store.ApplyLicense(license);
            _store.Save();
            return data.ContainsKey("message") ? Convert.ToString(data["message"]) : "License activated. CBT is now unlocked.";
        }

        public string PullPackage(string fallbackPin)
        {
            RequireToken();
            var json = RequestAuthenticated("GET", NormalizeCloudUrl(_store.State.CloudUrl) + "/api/exams/cbt/offline-sync/", "");
            var result = _packages.ImportPackageJson(json, fallbackPin);
            _store.State.LastSyncAt = JsonUtil.IsoNow();
            _store.Save();
            return result;
        }

        /// <summary>
        /// Uploads every submitted-but-not-yet-confirmed-synced session in one batch and
        /// applies the cloud's PER-ITEM response back to exactly those sessions - a session
        /// is only ever marked "synced" when the server's own response for that specific
        /// item said so. The previous implementation uploaded the same batch but then
        /// blanket-marked every submitted session as synced regardless of what the server
        /// actually reported per item, which could silently mark a result "synced" that the
        /// server had in fact rejected (e.g. a validation error on just that one item).
        ///
        /// Safe to call repeatedly / on a timer: the backend dedupes by session id
        /// (ExamAttempt.device_id, see _ingest_cbt_offline_result), so resending a session
        /// that already made it through just gets back "already synced" - never a
        /// duplicate. Throws on a hard failure (no login, network/timeout, bad response) so
        /// the "Upload Results"/"Upload Now" buttons can show the admin a real message;
        /// TryUploadResultsInBackground is the non-throwing wrapper for the unattended path.
        /// </summary>
        public string UploadResults()
        {
            RequireToken();
            List<SessionRecord> pending;
            lock (_store.Lock)
            {
                pending = _store.State.Sessions.Where(s => s.Status == "submitted" && s.SyncStatus != "synced").ToList();
            }
            if (pending.Count == 0)
            {
                lock (_store.Lock)
                {
                    _store.State.HasPendingUpload = false;
                    _store.Save();
                }
                return "Nothing to upload. All results are already synced.";
            }

            var json = _packages.BuildResultsPackageJson(pending);
            lock (_store.Lock)
            {
                _store.State.LastUploadAttemptAt = JsonUtil.IsoNow();
                _store.Save();
            }

            string response;
            try
            {
                response = RequestAuthenticated("POST", NormalizeCloudUrl(_store.State.CloudUrl) + "/api/exams/cbt/package/results/import/", json);
            }
            catch
            {
                // Nothing to undo here - a network/timeout failure never partially applied
                // anything server-side, so every session in `pending` is left exactly as it
                // was for the next tick or manual retry to pick back up.
                lock (_store.Lock)
                {
                    _store.State.HasPendingUpload = true;
                    _store.Save();
                }
                throw;
            }

            var data = JsonUtil.DeserializeObject(response);
            var processed = JsonUtil.List(data.ContainsKey("processed") ? data["processed"] : null);
            int synced, failed;
            lock (_store.Lock)
            {
                ApplyProcessedResults(pending, processed, out synced, out failed);
                _store.State.HasPendingUpload = _store.State.Sessions.Any(s => s.Status == "submitted" && s.SyncStatus != "synced");
                _store.State.LastSyncAt = JsonUtil.IsoNow();
                _store.Save();
            }

            return failed == 0
                ? "Uploaded " + synced + " result(s) to the cloud."
                : "Uploaded " + synced + " result(s); " + failed + " could not be confirmed yet and will retry automatically.";
        }

        /// <summary>
        /// Matches the cloud's per-item "processed" response (same order as the "results"
        /// list that was sent, since the backend loop appends in request order) back to the
        /// sessions that were uploaded, marking only confirmed items synced. If the counts
        /// don't line up 1:1 - which should never happen, but a malformed/truncated response
        /// is exactly the kind of thing a retry loop must not misinterpret - nothing is
        /// marked synced and every session's attempt count still goes up, so the next retry
        /// tries the whole batch again (harmless: the server dedupes by session id). Pure/
        /// static so it can be unit-tested without any network or store dependency.
        /// </summary>
        internal static void ApplyProcessedResults(List<SessionRecord> pending, List<object> processed, out int synced, out int failed)
        {
            synced = 0;
            failed = 0;
            if (processed.Count != pending.Count)
            {
                foreach (var session in pending) session.SyncAttempts += 1;
                failed = pending.Count;
                return;
            }
            for (var i = 0; i < pending.Count; i++)
            {
                var item = processed[i] as Dictionary<string, object>;
                var success = item != null && item.ContainsKey("success") && Convert.ToBoolean(item["success"]);
                if (success)
                {
                    pending[i].SyncStatus = "synced";
                    pending[i].SyncAttempts = 0;
                    pending[i].LastSyncError = "";
                    synced++;
                }
                else
                {
                    pending[i].SyncAttempts += 1;
                    pending[i].LastSyncError = ExtractProcessedMessage(item);
                    failed++;
                }
            }
        }

        private static string ExtractProcessedMessage(Dictionary<string, object> item)
        {
            if (item == null) return "Upload failed.";
            if (item.ContainsKey("message"))
            {
                var message = JsonUtil.Text(item["message"]);
                if (!string.IsNullOrWhiteSpace(message)) return message;
            }
            var data = item.ContainsKey("data") ? item["data"] as Dictionary<string, object> : null;
            if (data != null && data.ContainsKey("message"))
            {
                var message = JsonUtil.Text(data["message"]);
                if (!string.IsNullOrWhiteSpace(message)) return message;
            }
            return "Upload failed.";
        }

        /// <summary>
        /// Retry a previously failed upload. Called automatically on startup when
        /// HasPendingUpload is true and the admin is logged in (see MainForm/
        /// StartAutoResultSync) - kept as a thin alias so the existing "Upload Now" banner
        /// button keeps working unchanged.
        /// </summary>
        public string RetryPendingUpload()
        {
            if (!_store.State.HasPendingUpload) return null;
            return UploadResults();
        }

        /// <summary>
        /// Starts the background retry loop: an immediate first attempt a few seconds after
        /// login/launch, then every ResultSyncIntervalMs for as long as the app runs. This
        /// is what actually makes a failed or never-attempted upload retry on its own -
        /// without it, a result only ever gets (re)uploaded when an admin notices the
        /// "Pending" banner and clicks something. Safe to call once; a second call no-ops.
        /// </summary>
        public void StartAutoResultSync()
        {
            if (_resultSyncTimer != null) return;
            _resultSyncTimer = new System.Threading.Timer(_ => TryUploadResultsInBackground(), null, 5000, ResultSyncIntervalMs);
        }

        /// <summary>
        /// Fires one upload attempt right now on a background thread and returns
        /// immediately - called from LanServerService.OnResultSubmitted so a student's
        /// submission starts heading to the cloud within seconds under normal
        /// connectivity, instead of waiting for the next periodic tick. Never blocks the
        /// caller (which, for that call site, is the ThreadPool thread about to respond to
        /// the student) on any network I/O.
        /// </summary>
        public void TriggerResultSyncSoon()
        {
            new Task(() => TryUploadResultsInBackground()).Start();
        }

        /// <summary>
        /// Attempts to upload every pending result, swallowing every failure instead of
        /// throwing - this runs unattended (timer tick or a just-submitted-exam trigger), so
        /// there is no UI to show an exception to; the dashboard's "Pending" banner and each
        /// session's SyncStatus/LastSyncError already reflect whatever is still unsynced
        /// afterwards. The in-flight guard collapses overlapping calls (a timer tick landing
        /// at the same moment as a submission trigger) into a single attempt rather than two
        /// concurrent uploads of the same batch.
        /// </summary>
        public void TryUploadResultsInBackground()
        {
            if (_resultSyncInFlight) return;
            if (string.IsNullOrWhiteSpace(_store.State.AccessToken)) return;
            _resultSyncInFlight = true;
            try { UploadResults(); }
            catch { /* unattended - see summary above */ }
            finally { _resultSyncInFlight = false; }
        }

        public Dictionary<string, object> RegenerateExamPin(string examId)
        {
            RequireToken();
            if (string.IsNullOrWhiteSpace(examId))
            {
                throw new InvalidOperationException("Select an exam before generating a new PIN.");
            }
            var url = NormalizeCloudUrl(_store.State.CloudUrl) + "/api/exams/cbt/exams/" + Uri.EscapeDataString(examId) + "/pin/regenerate/";
            var response = RequestAuthenticated("POST", url, "{}");
            var data = JsonUtil.DeserializeObject(response);
            if (!data.ContainsKey("success") || !Convert.ToBoolean(data["success"]))
            {
                throw new InvalidOperationException(data.ContainsKey("message") ? Convert.ToString(data["message"]) : "Could not generate exam PIN.");
            }
            return data;
        }

        public Dictionary<string, object> CreateExam(ExamRecord exam, bool publish)
        {
            RequireToken();
            if (exam == null) throw new InvalidOperationException("Create the exam before sending it to cloud.");
            var start = DateTime.UtcNow;
            var end = start.AddDays(30);
            DateTime parsedStart;
            DateTime parsedEnd;
            if (DateTime.TryParse(exam.StartsAt, out parsedStart)) start = parsedStart.ToUniversalTime();
            if (DateTime.TryParse(exam.EndsAt, out parsedEnd)) end = parsedEnd.ToUniversalTime();
            if (end <= start) end = start.AddDays(30);

            var questions = new List<object>();
            foreach (var question in exam.Questions)
            {
                var options = question.Options ?? new List<string>();
                var correct = question.CorrectAnswer;
                if (string.IsNullOrWhiteSpace(correct) && options.Count > 0) correct = options[0];
                questions.Add(new Dictionary<string, object>
                {
                    { "text", question.Text ?? "" },
                    { "options", options },
                    { "correct_answer", correct ?? "" },
                    { "points", Math.Max(1, (int)Math.Round(question.Points <= 0 ? 1 : question.Points)) },
                    { "explanation", "" }
                });
            }

            var body = new Dictionary<string, object>
            {
                { "title", exam.Title ?? "" },
                { "duration_minutes", Math.Max(1, exam.DurationSeconds / 60) },
                { "start_date", start.ToString("o") },
                { "end_date", end.ToString("o") },
                { "instructions", exam.Instructions ?? "" },
                { "assessment_type", "exam" },
                { "is_published", publish },
                { "shuffle_questions", false },
                { "school_code", _store.State.SchoolCode ?? "" },
                { "questions", questions }
            };

            var response = RequestAuthenticated("POST", NormalizeCloudUrl(_store.State.CloudUrl) + "/api/app/exams/create/", JsonUtil.Serialize(body));
            var data = JsonUtil.DeserializeObject(response);
            if (!data.ContainsKey("success") || !Convert.ToBoolean(data["success"]))
            {
                throw new InvalidOperationException(data.ContainsKey("message") ? Convert.ToString(data["message"]) : "Could not create exam on cloud.");
            }
            return data;
        }

        public string DeleteResult(string examId, string studentId, string sessionId)
        {
            RequireToken();
            var body = new Dictionary<string, object>
            {
                { "exam_id", examId ?? "" },
                { "student_id", studentId ?? "" },
                { "session_id", sessionId ?? "" }
            };
            var response = RequestAuthenticated("POST", NormalizeCloudUrl(_store.State.CloudUrl) + "/api/exams/cbt/results/delete/", JsonUtil.Serialize(body));
            var data = JsonUtil.DeserializeObject(response);
            if (!data.ContainsKey("success") || !Convert.ToBoolean(data["success"]))
            {
                throw new InvalidOperationException(data.ContainsKey("message") ? Convert.ToString(data["message"]) : "Could not delete result.");
            }
            return data.ContainsKey("message") ? Convert.ToString(data["message"]) : "Result deleted.";
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

        /// <summary>
        /// Every cloud call that needs the admin's session goes through here instead of
        /// calling Request(...) directly. On a 401/expired-token response it tries one
        /// silent refresh (via the "remember me" RefreshToken saved at login) and retries
        /// the same call once with the new access token - the admin only sees the
        /// "Cloud Login Expired" prompt once the 7-day refresh token itself is gone.
        /// </summary>
        private string RequestAuthenticated(string method, string url, string body)
        {
            RequireToken();
            try
            {
                return Request(method, url, body, _store.State.AccessToken);
            }
            catch (CloudAuthExpiredException)
            {
                if (TryRefreshAccessToken())
                {
                    return Request(method, url, body, _store.State.AccessToken);
                }
                throw;
            }
        }

        /// <summary>
        /// Attempts to mint a fresh access token from the saved refresh token
        /// (POST /api/auth/refresh/). Returns false (never throws) on any failure -
        /// an invalid/expired/missing refresh token just means the admin has to sign
        /// in again, which the caller's own CloudAuthExpiredException handling covers.
        /// </summary>
        private bool TryRefreshAccessToken()
        {
            if (string.IsNullOrWhiteSpace(_store.State.RefreshToken)) return false;
            try
            {
                var body = new Dictionary<string, object> { { "refresh", _store.State.RefreshToken } };
                var response = Request("POST", NormalizeCloudUrl(_store.State.CloudUrl) + "/api/auth/refresh/", JsonUtil.Serialize(body), "");
                var data = JsonUtil.DeserializeObject(response);
                if (!data.ContainsKey("access") || string.IsNullOrWhiteSpace(Convert.ToString(data["access"])))
                {
                    return false;
                }
                _store.State.AccessToken = Convert.ToString(data["access"]);
                if (data.ContainsKey("refresh"))
                {
                    _store.State.RefreshToken = Convert.ToString(data["refresh"]);
                }
                _store.Save();
                return true;
            }
            catch
            {
                return false;
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
                var statusCode = 0;
                if (ex.Response != null)
                {
                    var httpResponse = ex.Response as HttpWebResponse;
                    if (httpResponse != null) statusCode = (int)httpResponse.StatusCode;
                    using (var stream = ex.Response.GetResponseStream())
                    using (var reader = new StreamReader(stream ?? Stream.Null))
                    {
                        var details = reader.ReadToEnd();
                        if (!string.IsNullOrWhiteSpace(details))
                        {
                            if (details.IndexOf("<!DOCTYPE", StringComparison.OrdinalIgnoreCase) >= 0 ||
                                details.IndexOf("<html", StringComparison.OrdinalIgnoreCase) >= 0)
                            {
                                if (statusCode == 404)
                                {
                                    message = "The website does not have this CBT PIN generation endpoint yet. Deploy the latest SchoolDom backend, then try again.";
                                }
                                else
                                {
                                    message = "The website returned an HTML error page instead of JSON. Status code: " + statusCode + ".";
                                }
                            }
                            else
                            {
                                message = ExtractJsonMessage(details, details);
                            }
                        }
                    }
                }
                if (statusCode == 401 || IsExpiredTokenMessage(message))
                {
                    throw new CloudAuthExpiredException("Your saved cloud login has expired. Please sign in again, then try the action once more.");
                }
                throw new InvalidOperationException("Cloud request failed: " + message);
            }
        }

        /// <summary>
        /// The backend's error responses are JSON with a "message" field (e.g. the CBT
        /// license 403: {"success": false, "message": "...", "license": {...}}). Surfacing
        /// that field instead of the raw JSON blob is what lets MessageBox.Show(ex.Message)
        /// callers (Sync Now, LAN Server start, ...) show admins a clear sentence.
        /// </summary>
        private static string ExtractJsonMessage(string details, string fallback)
        {
            try
            {
                var data = JsonUtil.DeserializeObject(details);
                if (data.ContainsKey("message"))
                {
                    var message = Convert.ToString(data["message"]);
                    if (!string.IsNullOrWhiteSpace(message)) return message;
                }
            }
            catch { }
            return fallback;
        }

        private static bool IsExpiredTokenMessage(string message)
        {
            var value = (message ?? "").ToLowerInvariant();
            return value.IndexOf("token_not_valid", StringComparison.OrdinalIgnoreCase) >= 0 ||
                   value.IndexOf("token is expired", StringComparison.OrdinalIgnoreCase) >= 0 ||
                   value.IndexOf("given token not valid", StringComparison.OrdinalIgnoreCase) >= 0 ||
                   value.IndexOf("access token", StringComparison.OrdinalIgnoreCase) >= 0 && value.IndexOf("expired", StringComparison.OrdinalIgnoreCase) >= 0;
        }
    }
}
