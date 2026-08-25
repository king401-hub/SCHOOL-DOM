using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Text;

namespace SchoolDom.Rfid.Win7
{
    // Thrown when the saved access token is missing/expired - callers catch this
    // specifically to trigger LoginForm instead of showing a generic error.
    public class CloudAuthExpiredException : InvalidOperationException
    {
        public CloudAuthExpiredException(string message) : base(message) { }
    }

    // A card scanned/assigned against a card_uid that's already active on a
    // different student (Section 4d) - callers catch this to show the "reassign?"
    // confirmation instead of a plain error.
    public class CardAssignmentConflictException : InvalidOperationException
    {
        public string ConflictingStudentName { get; private set; }
        public string ConflictingCardUid { get; private set; }

        public CardAssignmentConflictException(string message, string conflictingStudentName, string conflictingCardUid)
            : base(message)
        {
            ConflictingStudentName = conflictingStudentName;
            ConflictingCardUid = conflictingCardUid;
        }
    }

    internal sealed class FlushResult
    {
        public int Succeeded;
        public int Failed;
        public int RemainingInQueue;
    }

    // Everything the desktop app sends to/pulls from the SchoolDom API. Modeled
    // directly on SchoolDom.Cbt.Win7's CloudSyncService (same HttpWebRequest +
    // JsonUtil approach, same auth-expiry detection) so both apps behave
    // identically against flaky school networks and old-Windows TLS quirks.
    internal sealed class SyncService
    {
        private readonly LocalStore _store;

        public SyncService(LocalStore store)
        {
            _store = store;
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
            var normalized = NormalizeCloudUrl(cloudUrl);
            var response = RequestRaw("POST", normalized + "/api/auth/login/", JsonUtil.Serialize(body), null);
            if (response.StatusCode < 200 || response.StatusCode >= 300)
            {
                throw new InvalidOperationException(ExtractJsonMessage(response.Body, "Sign-in failed. Check your email and password."));
            }

            var data = JsonUtil.DeserializeObject(response.Body);
            if (!data.ContainsKey("access"))
            {
                throw new InvalidOperationException("Sign-in succeeded but no access token was returned.");
            }

            _store.State.CloudUrl = normalized;
            _store.State.AccessToken = Convert.ToString(data["access"]);

            var school = data.ContainsKey("school") ? data["school"] as Dictionary<string, object> : null;
            if (school != null)
            {
                if (school.ContainsKey("name")) _store.State.SchoolName = Convert.ToString(school["name"]);
                if (school.ContainsKey("school_code")) _store.State.SchoolCode = Convert.ToString(school["school_code"]);
            }
            var user = data.ContainsKey("user") ? data["user"] as Dictionary<string, object> : null;
            if (user != null)
            {
                var first = user.ContainsKey("first_name") ? Convert.ToString(user["first_name"]) : "";
                var last = user.ContainsKey("last_name") ? Convert.ToString(user["last_name"]) : "";
                var full = (first + " " + last).Trim();
                if (full.Length > 0) _store.State.OperatorName = full;
            }

            _store.Save();
            return "Signed in to SchoolDom cloud.";
        }

        public void SignOut()
        {
            _store.State.AccessToken = null;
            _store.Save();
        }

        // Section 1d/4e - refreshes the local card_uid -> student cache every scan
        // is checked against, so a network blip after login never blocks matching.
        public List<CardAssignmentRecord> PullCardAssignments()
        {
            var response = Request("GET", "/api/rfid/card-assignments/", "");
            var data = JsonUtil.DeserializeObject(response.Body);
            var rows = data.ContainsKey("data") ? data["data"] as object[] : null;
            var result = new List<CardAssignmentRecord>();
            if (rows != null)
            {
                foreach (var row in rows)
                {
                    var map = row as Dictionary<string, object>;
                    if (map == null) continue;
                    result.Add(new CardAssignmentRecord
                    {
                        StudentId = JsonUtil.Text(map.ContainsKey("student_id") ? map["student_id"] : null),
                        StudentName = JsonUtil.Text(map.ContainsKey("student_name") ? map["student_name"] : null),
                        CardUid = JsonUtil.Text(map.ContainsKey("card_uid") ? map["card_uid"] : null),
                        Status = "active"
                    });
                }
            }
            _store.State.CardAssignments = result;
            _store.State.LastAssignmentsPullAtUtc = JsonUtil.IsoNow();
            _store.Save();
            return result;
        }

        // Section 4b/4c/4d. Throws CardAssignmentConflictException (not force) when
        // the card or student already has an active link, so the caller can show
        // the "reassign?" confirmation and retry with force=true.
        public CardAssignmentRecord AssignCard(string cardUid, string studentId, string studentName, bool force)
        {
            var body = new Dictionary<string, object>
            {
                { "card_uid", cardUid }, { "student_id", studentId }, { "force", force }
            };
            var response = Request("POST", "/api/rfid/card-assignments/assign/", JsonUtil.Serialize(body));

            if (response.StatusCode == 409)
            {
                var conflictData = JsonUtil.DeserializeObject(response.Body);
                throw new CardAssignmentConflictException(
                    JsonUtil.Text(conflictData.ContainsKey("message") ? conflictData["message"] : null, "This card or student already has an active assignment."),
                    conflictData.ContainsKey("conflicting_student_name") ? JsonUtil.Text(conflictData["conflicting_student_name"]) : null,
                    conflictData.ContainsKey("conflicting_card_uid") ? JsonUtil.Text(conflictData["conflicting_card_uid"]) : null);
            }
            if (response.StatusCode < 200 || response.StatusCode >= 300)
            {
                throw new InvalidOperationException(ExtractJsonMessage(response.Body, "Could not assign this card."));
            }

            var record = new CardAssignmentRecord { StudentId = studentId, StudentName = studentName, CardUid = cardUid, Status = "active" };
            var existing = _store.State.CardAssignments.FirstOrDefault(a => string.Equals(a.StudentId, studentId, StringComparison.OrdinalIgnoreCase));
            if (existing != null) _store.State.CardAssignments.Remove(existing);
            _store.State.CardAssignments.Add(record);
            _store.Save();
            return record;
        }

        // Feeds CardAssignmentForm/BulkAssignForm's pickers (Section 4b/4c).
        public List<ClassOption> PullClasses()
        {
            var response = Request("GET", "/api/rfid/classes/", "");
            var data = JsonUtil.DeserializeObject(response.Body);
            var rows = data.ContainsKey("data") ? data["data"] as object[] : null;
            var result = new List<ClassOption>();
            if (rows != null)
            {
                foreach (var row in rows)
                {
                    var map = row as Dictionary<string, object>;
                    if (map == null) continue;
                    result.Add(new ClassOption
                    {
                        Id = JsonUtil.Text(map.ContainsKey("id") ? map["id"] : null),
                        Label = JsonUtil.Text(map.ContainsKey("label") ? map["label"] : null)
                    });
                }
            }
            return result;
        }

        public List<StudentOption> PullStudents(string classId, string search, bool excludeAssigned)
        {
            var url = "/api/rfid/students/?exclude_assigned=" + (excludeAssigned ? "true" : "false");
            if (!string.IsNullOrEmpty(classId)) url += "&class_id=" + Uri.EscapeDataString(classId);
            if (!string.IsNullOrEmpty(search)) url += "&search=" + Uri.EscapeDataString(search);

            var response = Request("GET", url, "");
            var data = JsonUtil.DeserializeObject(response.Body);
            var rows = data.ContainsKey("data") ? data["data"] as object[] : null;
            var result = new List<StudentOption>();
            if (rows != null)
            {
                foreach (var row in rows)
                {
                    var map = row as Dictionary<string, object>;
                    if (map == null) continue;
                    result.Add(new StudentOption
                    {
                        Id = JsonUtil.Text(map.ContainsKey("id") ? map["id"] : null),
                        Name = JsonUtil.Text(map.ContainsKey("name") ? map["name"] : null),
                        StudentCode = JsonUtil.Text(map.ContainsKey("student_id") ? map["student_id"] : null),
                        ClassName = JsonUtil.Text(map.ContainsKey("class_name") ? map["class_name"] : null),
                        HasActiveCard = map.ContainsKey("has_active_card") && Convert.ToBoolean(map["has_active_card"])
                    });
                }
            }
            return result;
        }

        public void RevokeCard(string cardUid, string studentId)
        {
            var body = new Dictionary<string, object> { { "card_uid", cardUid ?? "" }, { "student_id", studentId ?? "" } };
            var response = Request("POST", "/api/rfid/card-assignments/revoke/", JsonUtil.Serialize(body));
            if (response.StatusCode < 200 || response.StatusCode >= 300)
            {
                throw new InvalidOperationException(ExtractJsonMessage(response.Body, "Could not unassign this card."));
            }

            var existing = _store.State.CardAssignments.FirstOrDefault(a =>
                (!string.IsNullOrEmpty(cardUid) && string.Equals(a.CardUid, cardUid, StringComparison.OrdinalIgnoreCase)) ||
                (!string.IsNullOrEmpty(studentId) && string.Equals(a.StudentId, studentId, StringComparison.OrdinalIgnoreCase)));
            if (existing != null) _store.State.CardAssignments.Remove(existing);
            _store.Save();
        }

        // Section 3 - flushes the offline queue oldest-first, stopping the whole
        // batch (not just one record) on the first sign that the network or the
        // session is the problem, so a dead connection doesn't burn through 200
        // queued records as 200 individual failures/log entries.
        public FlushResult FlushPendingQueue()
        {
            var result = new FlushResult();
            var queue = _store.State.PendingAttendance;

            foreach (var record in queue.OrderBy(r => r.ScannedAtUtc).ToList())
            {
                AttendanceScanOutcome outcome;
                try
                {
                    outcome = PushAttendanceScan(record);
                }
                catch (CloudAuthExpiredException)
                {
                    result.RemainingInQueue = queue.Count;
                    throw;
                }
                catch (Exception ex)
                {
                    record.AttemptCount++;
                    record.LastAttemptError = ex.Message;
                    _store.Save();
                    result.Failed++;
                    break; // network/server is down - stop hammering, try again next tick
                }

                if (outcome == AttendanceScanOutcome.Success || outcome == AttendanceScanOutcome.AlreadyRecorded)
                {
                    queue.Remove(record);
                    result.Succeeded++;
                }
                else
                {
                    // Card was unassigned/revoked between the scan and now - this
                    // specific record can never succeed; drop it rather than retry forever.
                    queue.Remove(record);
                    result.Failed++;
                }
            }

            _store.Save();
            result.RemainingInQueue = queue.Count;
            return result;
        }

        private AttendanceScanOutcome PushAttendanceScan(PendingAttendanceRecord record)
        {
            var body = new Dictionary<string, object>
            {
                { "card_uid", record.CardUid },
                { "idempotency_key", record.IdempotencyKey },
                { "device_id", _store.State.DeviceId },
            };
            var response = Request("POST", "/api/rfid/attendance/scan/", JsonUtil.Serialize(body));

            if (response.StatusCode == 404)
            {
                var data = JsonUtil.DeserializeObject(response.Body);
                var unregistered = data.ContainsKey("unregistered") && Convert.ToBoolean(data["unregistered"]);
                if (unregistered) return AttendanceScanOutcome.CardNoLongerValid;
            }
            if (response.StatusCode < 200 || response.StatusCode >= 300)
            {
                throw new InvalidOperationException(ExtractJsonMessage(response.Body, "Could not sync this attendance record."));
            }

            var success = JsonUtil.DeserializeObject(response.Body);
            var duplicate = success.ContainsKey("duplicate") && Convert.ToBoolean(success["duplicate"]);
            return duplicate ? AttendanceScanOutcome.AlreadyRecorded : AttendanceScanOutcome.Success;
        }

        private enum AttendanceScanOutcome { Success, AlreadyRecorded, CardNoLongerValid }

        private HttpApiResponse Request(string method, string path, string body)
        {
            if (string.IsNullOrWhiteSpace(_store.State.AccessToken))
            {
                throw new CloudAuthExpiredException("Sign in before syncing.");
            }
            var url = NormalizeCloudUrl(_store.State.CloudUrl) + path;
            var response = RequestRaw(method, url, body, _store.State.AccessToken);
            if (response.StatusCode == 401 || IsExpiredTokenMessage(response.Body))
            {
                throw new CloudAuthExpiredException("Your saved sign-in has expired. Please sign in again.");
            }
            return response;
        }

        private struct HttpApiResponse
        {
            public int StatusCode;
            public string Body;
        }

        private static HttpApiResponse RequestRaw(string method, string url, string body, string accessToken)
        {
            var request = (HttpWebRequest)WebRequest.Create(url);
            request.Method = method;
            request.Timeout = 30000;
            request.ContentType = "application/json";
            request.UserAgent = "SchoolDom-RFID-Win7";
            if (!string.IsNullOrWhiteSpace(accessToken))
            {
                request.Headers["Authorization"] = "Bearer " + accessToken.Trim();
            }
            if (method == "POST" || method == "PUT")
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
                    return new HttpApiResponse { StatusCode = (int)response.StatusCode, Body = reader.ReadToEnd() };
                }
            }
            catch (WebException ex)
            {
                var httpResponse = ex.Response as HttpWebResponse;
                if (httpResponse != null)
                {
                    using (var stream = httpResponse.GetResponseStream())
                    using (var reader = new StreamReader(stream ?? Stream.Null))
                    {
                        return new HttpApiResponse { StatusCode = (int)httpResponse.StatusCode, Body = reader.ReadToEnd() };
                    }
                }
                // No response at all - DNS failure, timeout, connection refused (network is down).
                throw new InvalidOperationException("Network error: " + ex.Message, ex);
            }
        }

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
                   value.IndexOf("given token not valid", StringComparison.OrdinalIgnoreCase) >= 0;
        }
    }
}
