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

    // Thrown only when the server genuinely could not be reached at all (DNS
    // failure, timeout, connection refused - see RequestRaw's WebException
    // catch with ex.Response == null). Distinct from a definite HTTP error
    // response (400/500 with a body), which means the server WAS reached and
    // rejected this one request specifically - FlushPendingQueue uses this
    // distinction to decide whether stopping the whole batch makes sense.
    public class NetworkUnavailableException : InvalidOperationException
    {
        public NetworkUnavailableException(string message, Exception inner) : base(message, inner) { }
    }

    // A card scanned/assigned against a card_uid that's already active on a
    // different person (Section 4d) - callers catch this to show the rich
    // "already assigned to X" confirmation (name/photo/class) instead of a
    // plain error, and require an explicit unassign before reassigning.
    public class CardAssignmentConflictException : InvalidOperationException
    {
        public string ConflictingPersonName { get; private set; }
        public string ConflictingPersonRoleLabel { get; private set; }
        public string ConflictingPersonClassName { get; private set; }
        public string ConflictingPersonPhotoUrl { get; private set; }
        public string ConflictingCardUid { get; private set; }

        public CardAssignmentConflictException(
            string message, string conflictingPersonName, string conflictingPersonRoleLabel,
            string conflictingPersonClassName, string conflictingPersonPhotoUrl, string conflictingCardUid)
            : base(message)
        {
            ConflictingPersonName = conflictingPersonName;
            ConflictingPersonRoleLabel = conflictingPersonRoleLabel;
            ConflictingPersonClassName = conflictingPersonClassName;
            ConflictingPersonPhotoUrl = conflictingPersonPhotoUrl;
            ConflictingCardUid = conflictingCardUid;
        }
    }

    // One flushed record's outcome - MainForm uses Action to update the live
    // feed row ("Clocked In"/"Clocked Out") once the server has actually
    // resolved which one it was, matched back by IdempotencyKey.
    internal sealed class SyncedScanResult
    {
        public string IdempotencyKey;
        public string Action; // "clock_in" | "clock_out" | null
    }

    internal sealed class FlushResult
    {
        public int Succeeded;
        public int Failed;
        public int RemainingInQueue;
        public List<SyncedScanResult> Synced = new List<SyncedScanResult>();
    }

    // Everything the desktop app sends to/pulls from the SchoolDom API. Modeled
    // directly on SchoolDom.Cbt.Win7's CloudSyncService (same HttpWebRequest +
    // JsonUtil approach, same auth-expiry detection) so both apps behave
    // identically against flaky school networks and old-Windows TLS quirks.
    //
    // Called from both the UI thread (user-initiated actions - login, assign,
    // search) and a background thread (MainForm's periodic sync timer, see
    // RunFlush there) - every method that touches _store.State holds
    // _store.StateLock for exactly that part, never around the network I/O
    // itself (which would serialize an unrelated UI-thread action behind a
    // slow background request for no reason).
    internal sealed class SyncService
    {
        // A record that's been rejected (not "too soon", an actual rejection) this
        // many times is treated as permanently unresolvable and dropped instead of
        // retried forever - "already clocked out today" cannot become true again
        // until tomorrow, and there's no value in keeping such a record queued
        // indefinitely once that's been confirmed repeatedly.
        private const int MaxAttemptsBeforeAbandoning = 20;

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

            var school = data.ContainsKey("school") ? data["school"] as Dictionary<string, object> : null;
            var user = data.ContainsKey("user") ? data["user"] as Dictionary<string, object> : null;

            lock (_store.StateLock)
            {
                _store.State.CloudUrl = normalized;
                _store.State.AccessToken = Convert.ToString(data["access"]);

                if (school != null)
                {
                    if (school.ContainsKey("name")) _store.State.SchoolName = Convert.ToString(school["name"]);
                    if (school.ContainsKey("school_code")) _store.State.SchoolCode = Convert.ToString(school["school_code"]);
                }
                if (user != null)
                {
                    var first = user.ContainsKey("first_name") ? Convert.ToString(user["first_name"]) : "";
                    var last = user.ContainsKey("last_name") ? Convert.ToString(user["last_name"]) : "";
                    var full = (first + " " + last).Trim();
                    if (full.Length > 0) _store.State.OperatorName = full;
                }
                _store.Save();
            }
            return "Signed in to SchoolDom cloud.";
        }

        public void SignOut()
        {
            lock (_store.StateLock)
            {
                _store.State.AccessToken = null;
                _store.Save();
            }
        }

        // Section 1d/4e - refreshes the local card_uid -> person cache every scan
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
                        PersonId = JsonUtil.Text(map.ContainsKey("person_id") ? map["person_id"] : null),
                        PersonName = JsonUtil.Text(map.ContainsKey("person_name") ? map["person_name"] : null),
                        Role = JsonUtil.Text(map.ContainsKey("role") ? map["role"] : null),
                        CardUid = JsonUtil.Text(map.ContainsKey("card_uid") ? map["card_uid"] : null),
                        Status = "active"
                    });
                }
            }
            lock (_store.StateLock)
            {
                _store.State.CardAssignments = result;
                _store.State.LastAssignmentsPullAtUtc = JsonUtil.IsoNow();
                _store.Save();
            }
            return result;
        }

        // Section 4b/4c/4d. Throws CardAssignmentConflictException (not force) when
        // the card or person already has an active link, so the caller can show
        // the "reassign?" confirmation and retry with force=true. personId can be
        // any tenant user - student, teacher, or admin (admins can assign
        // themselves a card too).
        public CardAssignmentRecord AssignCard(string cardUid, string personId, string personName, string role, bool force)
        {
            var body = new Dictionary<string, object>
            {
                { "card_uid", cardUid }, { "person_id", personId }, { "force", force }
            };
            var response = Request("POST", "/api/rfid/card-assignments/assign/", JsonUtil.Serialize(body));

            if (response.StatusCode == 409)
            {
                var conflictData = JsonUtil.DeserializeObject(response.Body);
                var conflictingPerson = conflictData.ContainsKey("conflicting_person") ? conflictData["conflicting_person"] as Dictionary<string, object> : null;
                throw new CardAssignmentConflictException(
                    JsonUtil.Text(conflictData.ContainsKey("message") ? conflictData["message"] : null, "This card or person already has an active assignment."),
                    conflictingPerson != null ? JsonUtil.Text(conflictingPerson.ContainsKey("name") ? conflictingPerson["name"] : null) : null,
                    conflictingPerson != null ? JsonUtil.Text(conflictingPerson.ContainsKey("role_label") ? conflictingPerson["role_label"] : null) : null,
                    conflictingPerson != null ? JsonUtil.Text(conflictingPerson.ContainsKey("class_name") ? conflictingPerson["class_name"] : null) : null,
                    conflictingPerson != null ? JsonUtil.Text(conflictingPerson.ContainsKey("photo_url") ? conflictingPerson["photo_url"] : null) : null,
                    conflictData.ContainsKey("conflicting_card_uid") ? JsonUtil.Text(conflictData["conflicting_card_uid"]) : null);
            }
            if (response.StatusCode < 200 || response.StatusCode >= 300)
            {
                throw new InvalidOperationException(ExtractJsonMessage(response.Body, "Could not assign this card."));
            }

            var record = new CardAssignmentRecord { PersonId = personId, PersonName = personName, Role = role, CardUid = cardUid, Status = "active" };
            lock (_store.StateLock)
            {
                var existing = _store.State.CardAssignments.FirstOrDefault(a => string.Equals(a.PersonId, personId, StringComparison.OrdinalIgnoreCase));
                if (existing != null) _store.State.CardAssignments.Remove(existing);
                _store.State.CardAssignments.Add(record);
                _store.Save();
            }
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

        // roles: null/empty = every assignable role (student/teacher/staff/admin);
        // otherwise a comma-separated list, e.g. "student" for Bulk Assign.
        public List<PersonOption> PullPeople(string classId, string search, string roles, bool excludeAssigned)
        {
            var url = "/api/rfid/people/?exclude_assigned=" + (excludeAssigned ? "true" : "false");
            if (!string.IsNullOrEmpty(classId)) url += "&class_id=" + Uri.EscapeDataString(classId);
            if (!string.IsNullOrEmpty(search)) url += "&search=" + Uri.EscapeDataString(search);
            if (!string.IsNullOrEmpty(roles)) url += "&roles=" + Uri.EscapeDataString(roles);

            var response = Request("GET", url, "");
            var data = JsonUtil.DeserializeObject(response.Body);
            var rows = data.ContainsKey("data") ? data["data"] as object[] : null;
            var result = new List<PersonOption>();
            if (rows != null)
            {
                foreach (var row in rows)
                {
                    var map = row as Dictionary<string, object>;
                    if (map == null) continue;
                    result.Add(new PersonOption
                    {
                        Id = JsonUtil.Text(map.ContainsKey("id") ? map["id"] : null),
                        Name = JsonUtil.Text(map.ContainsKey("name") ? map["name"] : null),
                        Role = JsonUtil.Text(map.ContainsKey("role") ? map["role"] : null),
                        RoleLabel = JsonUtil.Text(map.ContainsKey("role_label") ? map["role_label"] : null),
                        PhotoUrl = JsonUtil.Text(map.ContainsKey("photo_url") ? map["photo_url"] : null),
                        StudentCode = JsonUtil.Text(map.ContainsKey("student_id") ? map["student_id"] : null),
                        ClassName = JsonUtil.Text(map.ContainsKey("class_name") ? map["class_name"] : null),
                        HasActiveCard = map.ContainsKey("has_active_card") && Convert.ToBoolean(map["has_active_card"])
                    });
                }
            }
            return result;
        }

        public void RevokeCard(string cardUid, string personId)
        {
            var body = new Dictionary<string, object> { { "card_uid", cardUid ?? "" }, { "person_id", personId ?? "" } };
            var response = Request("POST", "/api/rfid/card-assignments/revoke/", JsonUtil.Serialize(body));
            if (response.StatusCode < 200 || response.StatusCode >= 300)
            {
                throw new InvalidOperationException(ExtractJsonMessage(response.Body, "Could not unassign this card."));
            }

            lock (_store.StateLock)
            {
                var existing = _store.State.CardAssignments.FirstOrDefault(a =>
                    (!string.IsNullOrEmpty(cardUid) && string.Equals(a.CardUid, cardUid, StringComparison.OrdinalIgnoreCase)) ||
                    (!string.IsNullOrEmpty(personId) && string.Equals(a.PersonId, personId, StringComparison.OrdinalIgnoreCase)));
                if (existing != null) _store.State.CardAssignments.Remove(existing);
                _store.Save();
            }
        }

        // Attendance History screen - always fetched fresh, never cached locally.
        public List<AttendanceHistoryEntry> PullAttendanceHistory(string dateIso)
        {
            var url = "/api/rfid/attendance/history/";
            if (!string.IsNullOrEmpty(dateIso)) url += "?date=" + Uri.EscapeDataString(dateIso);

            var response = Request("GET", url, "");
            var data = JsonUtil.DeserializeObject(response.Body);
            var rows = data.ContainsKey("data") ? data["data"] as object[] : null;
            var result = new List<AttendanceHistoryEntry>();
            if (rows != null)
            {
                foreach (var row in rows)
                {
                    var map = row as Dictionary<string, object>;
                    if (map == null) continue;
                    result.Add(new AttendanceHistoryEntry
                    {
                        PersonName = JsonUtil.Text(map.ContainsKey("person_name") ? map["person_name"] : null),
                        Role = JsonUtil.Text(map.ContainsKey("role") ? map["role"] : null),
                        ClockInAt = ParseIsoOrNull(map.ContainsKey("clock_in_at") ? map["clock_in_at"] : null),
                        ClockOutAt = ParseIsoOrNull(map.ContainsKey("clock_out_at") ? map["clock_out_at"] : null),
                        Status = JsonUtil.Text(map.ContainsKey("status") ? map["status"] : null),
                        CardUid = JsonUtil.Text(map.ContainsKey("card_uid") ? map["card_uid"] : null),
                    });
                }
            }
            return result;
        }

        private static DateTime? ParseIsoOrNull(object value)
        {
            if (value == null) return null;
            DateTime parsed;
            if (DateTime.TryParse(Convert.ToString(value), null, System.Globalization.DateTimeStyles.RoundtripKind, out parsed))
                return parsed.ToLocalTime();
            return null;
        }

        // Section 3 - flushes the offline queue oldest-first, stopping the whole
        // batch (not just one record) on the first sign that the network or the
        // session is the problem, so a dead connection doesn't burn through 200
        // queued records as 200 individual failures/log entries.
        public FlushResult FlushPendingQueue()
        {
            var result = new FlushResult();
            List<PendingAttendanceRecord> snapshot;
            lock (_store.StateLock)
            {
                snapshot = _store.State.PendingAttendance.OrderBy(r => r.ScannedAtUtc).ToList();
            }

            foreach (var record in snapshot)
            {
                PushScanResult pushResult;
                try
                {
                    pushResult = PushAttendanceScan(record);
                }
                catch (CloudAuthExpiredException)
                {
                    lock (_store.StateLock) { result.RemainingInQueue = _store.State.PendingAttendance.Count; }
                    throw;
                }
                catch (NetworkUnavailableException ex)
                {
                    // The server genuinely could not be reached - every other queued
                    // record would fail identically right now, so stop this pass
                    // rather than burning through the whole queue for no reason.
                    lock (_store.StateLock)
                    {
                        record.AttemptCount++;
                        record.LastAttemptError = ex.Message;
                        _store.Save();
                    }
                    result.Failed++;
                    break;
                }
                catch (Exception ex)
                {
                    // The server WAS reached and rejected this one record specifically
                    // (e.g. "already clocked out today") - that says nothing about
                    // whether the next queued record would also fail, so keep going
                    // instead of blocking everything behind it. This is the fix for
                    // records getting permanently stuck: previously any failure here
                    // broke the whole batch, so one record that could never succeed
                    // (like a third scan of someone already clocked out for the day)
                    // silently blocked every record queued after it, forever - one
                    // such record was found with AttemptCount=91 while newer, valid
                    // scans sat behind it untouched.
                    bool abandoned;
                    lock (_store.StateLock)
                    {
                        record.AttemptCount++;
                        record.LastAttemptError = ex.Message;
                        abandoned = record.AttemptCount >= MaxAttemptsBeforeAbandoning;
                        if (abandoned) _store.State.PendingAttendance.Remove(record);
                        _store.Save();
                    }
                    result.Failed++;
                    continue;
                }

                if (pushResult.Outcome == AttendanceScanOutcome.TooSoonRetryLater)
                {
                    // The 3-hour clock-in/clock-out gate hasn't cleared yet - this
                    // isn't a failure, it's not due. Leave it queued and move on to
                    // the next record instead of blocking the whole batch behind it.
                    continue;
                }

                lock (_store.StateLock)
                {
                    // Card was unassigned/revoked between the scan and now (CardNoLongerValid)
                    // - that specific record can never succeed; drop it rather than retry forever.
                    _store.State.PendingAttendance.Remove(record);
                    _store.Save();
                }

                if (pushResult.Outcome == AttendanceScanOutcome.Success || pushResult.Outcome == AttendanceScanOutcome.AlreadyRecorded)
                {
                    result.Succeeded++;
                    result.Synced.Add(new SyncedScanResult { IdempotencyKey = record.IdempotencyKey, Action = pushResult.Action });
                }
                else
                {
                    result.Failed++;
                }
            }

            lock (_store.StateLock) { result.RemainingInQueue = _store.State.PendingAttendance.Count; }
            return result;
        }

        private struct PushScanResult
        {
            public AttendanceScanOutcome Outcome;
            public string Action;
        }

        private PushScanResult PushAttendanceScan(PendingAttendanceRecord record)
        {
            string deviceId;
            lock (_store.StateLock) { deviceId = _store.State.DeviceId; }

            var body = new Dictionary<string, object>
            {
                { "card_uid", record.CardUid },
                { "idempotency_key", record.IdempotencyKey },
                { "device_id", deviceId },
            };
            var response = Request("POST", "/api/rfid/attendance/scan/", JsonUtil.Serialize(body));

            if (response.StatusCode == 404)
            {
                var data = JsonUtil.DeserializeObject(response.Body);
                var unregistered = data.ContainsKey("unregistered") && Convert.ToBoolean(data["unregistered"]);
                if (unregistered) return new PushScanResult { Outcome = AttendanceScanOutcome.CardNoLongerValid };
            }
            if (response.StatusCode == 400)
            {
                var data = JsonUtil.DeserializeObject(response.Body);
                var tooSoon = data.ContainsKey("too_soon") && Convert.ToBoolean(data["too_soon"]);
                if (tooSoon) return new PushScanResult { Outcome = AttendanceScanOutcome.TooSoonRetryLater };
            }
            if (response.StatusCode < 200 || response.StatusCode >= 300)
            {
                throw new InvalidOperationException(ExtractJsonMessage(response.Body, "Could not sync this attendance record."));
            }

            var success = JsonUtil.DeserializeObject(response.Body);
            var duplicate = success.ContainsKey("duplicate") && Convert.ToBoolean(success["duplicate"]);
            var action = success.ContainsKey("action") ? JsonUtil.Text(success["action"]) : null;
            return new PushScanResult
            {
                Outcome = duplicate ? AttendanceScanOutcome.AlreadyRecorded : AttendanceScanOutcome.Success,
                Action = action
            };
        }

        private enum AttendanceScanOutcome { Success, AlreadyRecorded, CardNoLongerValid, TooSoonRetryLater }

        private HttpApiResponse Request(string method, string path, string body)
        {
            string accessToken, cloudUrl;
            lock (_store.StateLock)
            {
                accessToken = _store.State.AccessToken;
                cloudUrl = _store.State.CloudUrl;
            }
            if (string.IsNullOrWhiteSpace(accessToken))
            {
                throw new CloudAuthExpiredException("Sign in before syncing.");
            }
            var url = NormalizeCloudUrl(cloudUrl) + path;
            var response = RequestRaw(method, url, body, accessToken);
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
                throw new NetworkUnavailableException("Network error: " + ex.Message, ex);
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
