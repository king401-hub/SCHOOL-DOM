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

        public Dictionary<string, object> RegenerateExamPin(string examId)
        {
            RequireToken();
            if (string.IsNullOrWhiteSpace(examId))
            {
                throw new InvalidOperationException("Select an exam before generating a new PIN.");
            }
            var url = NormalizeCloudUrl(_store.State.CloudUrl) + "/api/exams/cbt/exams/" + Uri.EscapeDataString(examId) + "/pin/regenerate/";
            var response = Request("POST", url, "{}", _store.State.AccessToken);
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

            var response = Request("POST", NormalizeCloudUrl(_store.State.CloudUrl) + "/api/app/exams/create/", JsonUtil.Serialize(body), _store.State.AccessToken);
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
            var response = Request("POST", NormalizeCloudUrl(_store.State.CloudUrl) + "/api/exams/cbt/results/delete/", JsonUtil.Serialize(body), _store.State.AccessToken);
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
                                message = details;
                            }
                        }
                    }
                }
                throw new InvalidOperationException("Cloud request failed: " + message);
            }
        }
    }
}
