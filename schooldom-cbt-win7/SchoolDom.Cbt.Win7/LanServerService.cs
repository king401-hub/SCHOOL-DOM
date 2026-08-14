using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.NetworkInformation;
using System.Net.Sockets;
using System.Text;
using System.Threading;

namespace SchoolDom.Cbt.Win7
{
    public class LanServerService
    {
        public const int Port = 4785;
        public const int DiscoveryPort = 4786;
        private const string DiscoveryQuery = "SCHOOLDOM_CBT_DISCOVER";

        private readonly LocalStore _store;
        private TcpListener _listener;
        private UdpClient _discovery;
        private Thread _serverThread;
        private Thread _discoveryThread;
        private volatile bool _running;

        public LanServerService(LocalStore store)
        {
            _store = store;
        }

        public bool IsRunning
        {
            get { return _running; }
        }

        public string Start()
        {
            if (_running) return SnapshotMessage();
            _running = true;
            _listener = new TcpListener(IPAddress.Any, Port);
            _listener.Start();
            _serverThread = new Thread(ServerLoop) { IsBackground = true };
            _serverThread.Start();
            _discovery = new UdpClient(DiscoveryPort);
            _discoveryThread = new Thread(DiscoveryLoop) { IsBackground = true };
            _discoveryThread.Start();
            return SnapshotMessage();
        }

        public string Stop()
        {
            _running = false;
            try { if (_listener != null) _listener.Stop(); } catch { }
            try { if (_discovery != null) _discovery.Close(); } catch { }
            return "LAN server stopped.";
        }

        public List<string> LocalUrls()
        {
            return LocalAddresses().Select(address => "http://" + address + ":" + Port).ToList();
        }

        public string SnapshotMessage()
        {
            var urls = LocalUrls();
            if (!urls.Any()) return "LAN server running. No LAN address found yet.";
            return "LAN server running at:\r\n" + string.Join("\r\n", urls.ToArray());
        }

        private void ServerLoop()
        {
            while (_running)
            {
                try
                {
                    var client = _listener.AcceptTcpClient();
                    ThreadPool.QueueUserWorkItem(_ => HandleClient(client));
                }
                catch
                {
                    if (_running) Thread.Sleep(250);
                }
            }
        }

        private void DiscoveryLoop()
        {
            EnsureDiscoveryToken();
            while (_running)
            {
                try
                {
                    var remote = new IPEndPoint(IPAddress.Any, 0);
                    var bytes = _discovery.Receive(ref remote);
                    var message = Encoding.UTF8.GetString(bytes);
                    // Accept legacy unauthenticated queries from same subnet only,
                    // and authenticated queries with the correct token from anywhere.
                    var expectedQuery = DiscoveryQuery + ":" + _store.State.DiscoveryToken;
                    var legacyQuery = DiscoveryQuery;
                    if (message != expectedQuery && message != legacyQuery) continue;
                    // Reject legacy unauthenticated queries from outside the local subnet
                    if (message == legacyQuery && !IsSameSubnet(remote.Address)) continue;
                    var payload = Encoding.UTF8.GetBytes(JsonUtil.Serialize(new Dictionary<string, object>
                    {
                        { "type", "SCHOOLDOM_CBT_ADMIN" },
                        { "name", DisplaySchoolName() },
                        { "port", Port },
                        { "urls", LocalUrls() },
                        { "exams", _store.State.Exams.Count },
                        { "students", _store.State.Students.Count },
                    }));
                    _discovery.Send(payload, payload.Length, remote);
                }
                catch
                {
                    if (_running) Thread.Sleep(250);
                }
            }
        }

        private void EnsureDiscoveryToken()
        {
            if (!string.IsNullOrWhiteSpace(_store.State.DiscoveryToken)) return;
            _store.State.DiscoveryToken = Guid.NewGuid().ToString("N");
            _store.Save();
        }

        private bool IsSameSubnet(IPAddress remote)
        {
            foreach (var local in LocalAddresses())
            {
                var localParts = local.Split('.');
                var remoteParts = remote.ToString().Split('.');
                if (localParts.Length == 4 && remoteParts.Length == 4 &&
                    localParts[0] == remoteParts[0] && localParts[1] == remoteParts[1] && localParts[2] == remoteParts[2])
                    return true;
            }
            return false;
        }

        private void HandleClient(TcpClient client)
        {
            using (client)
            {
                try
                {
                    var stream = client.GetStream();
                    {
                        string method;
                        string path;
                        byte[] bodyBytes;
                        if (!TryReadHttpRequest(stream, out method, out path, out bodyBytes))
                        {
                            return;
                        }
                        // The body carries JSON (student answers, names, etc.) which can contain
                        // Yoruba/French/other non-ASCII text. Decoding it as UTF-8 (matching what
                        // LanClient.Post always sends) keeps those characters intact instead of
                        // turning them into '?' the way an ASCII decode would.
                        var bodyText = Encoding.UTF8.GetString(bodyBytes);

                        if (method == "OPTIONS")
                        {
                            WriteJson(stream, 200, new Dictionary<string, object> { { "ok", true } });
                        }
                        else if (method == "GET" && path == "/health")
                        {
                            WriteJson(stream, 200, SnapshotPayload());
                        }
                        else if (method == "GET" && path == "/api/package")
                        {
                            WriteJson(stream, 200, PackagePayload());
                        }
                        else if (method == "GET" && path == "/api/exams")
                        {
                            WriteJson(stream, 200, new Dictionary<string, object> { { "exams", _store.State.Exams } });
                        }
                        else if (method == "GET" && path == "/api/students")
                        {
                            WriteJson(stream, 200, new Dictionary<string, object> { { "students", _store.State.Students } });
                        }
                        else if (method == "POST" && path == "/api/login")
                        {
                            WriteJson(stream, 200, Login(bodyText));
                        }
                        else if (method == "POST" && path == "/api/start-session")
                        {
                            WriteJson(stream, 200, StartSession(bodyText));
                        }
                        else if (method == "GET" && path.StartsWith("/api/exams/", StringComparison.OrdinalIgnoreCase))
                        {
                            var examId = Uri.UnescapeDataString(path.Substring("/api/exams/".Length));
                            var exam = _store.State.Exams.FirstOrDefault(item => item.Id == examId);
                            if (exam == null) WriteJson(stream, 404, new Dictionary<string, object> { { "success", false }, { "message", "Exam not found." } });
                            else WriteJson(stream, 200, new Dictionary<string, object> { { "success", true }, { "exam", PublicExam(exam) }, { "payload", new Dictionary<string, object> { { "questions", exam.Questions } } } });
                        }
                        else if (method == "POST" && path.StartsWith("/api/sessions/", StringComparison.OrdinalIgnoreCase) && path.EndsWith("/begin", StringComparison.OrdinalIgnoreCase))
                        {
                            var sessionId = Uri.UnescapeDataString(path.Substring("/api/sessions/".Length, path.Length - "/api/sessions/".Length - "/begin".Length));
                            WriteJson(stream, 200, BeginExam(sessionId));
                        }
                        else if (method == "POST" && path.StartsWith("/api/sessions/", StringComparison.OrdinalIgnoreCase) && path.EndsWith("/answers", StringComparison.OrdinalIgnoreCase))
                        {
                            var sessionId = Uri.UnescapeDataString(path.Substring("/api/sessions/".Length, path.Length - "/api/sessions/".Length - "/answers".Length));
                            WriteJson(stream, 200, SaveAnswers(sessionId, bodyText));
                        }
                        else if (method == "POST" && path.StartsWith("/api/sessions/", StringComparison.OrdinalIgnoreCase) && path.EndsWith("/submit", StringComparison.OrdinalIgnoreCase))
                        {
                            var sessionId = Uri.UnescapeDataString(path.Substring("/api/sessions/".Length, path.Length - "/api/sessions/".Length - "/submit".Length));
                            WriteJson(stream, 200, SubmitSession(sessionId, bodyText));
                        }
                        else if (method == "POST" && path.StartsWith("/api/sessions/", StringComparison.OrdinalIgnoreCase) && path.EndsWith("/focus-loss", StringComparison.OrdinalIgnoreCase))
                        {
                            var sessionId = Uri.UnescapeDataString(path.Substring("/api/sessions/".Length, path.Length - "/api/sessions/".Length - "/focus-loss".Length));
                            WriteJson(stream, 200, LogFocusLoss(sessionId, bodyText));
                        }
                        else
                        {
                            WriteJson(stream, 404, new Dictionary<string, object> { { "success", false }, { "message", "Not found." } });
                        }
                    }
                }
                catch
                {
                    try
                    {
                        WriteJson(client.GetStream(), 500, new Dictionary<string, object> { { "success", false }, { "message", "LAN server error." } });
                    }
                    catch { }
                }
            }
        }

        /// <summary>
        /// Reads one HTTP request off the raw socket without ever decoding the body as text
        /// until we know it is complete. The previous implementation wrapped the stream in a
        /// StreamReader(Encoding.ASCII) and read Content-Length BYTES into a CHAR buffer, which
        /// both mis-sized multi-byte UTF-8 bodies and replaced every non-ASCII byte (Yoruba,
        /// French, curly quotes, ...) with '?'. Reading raw bytes and decoding the body as UTF-8
        /// (matching what LanClient always sends) keeps that text intact.
        /// </summary>
        private static bool TryReadHttpRequest(NetworkStream stream, out string method, out string path, out byte[] bodyBytes)
        {
            method = "";
            path = "/";
            bodyBytes = new byte[0];

            var raw = new MemoryStream();
            var chunk = new byte[8192];
            int headerEnd = -1;
            while (headerEnd < 0)
            {
                var read = stream.Read(chunk, 0, chunk.Length);
                if (read <= 0) return raw.Length > 0;
                raw.Write(chunk, 0, read);
                headerEnd = FindHeaderEnd(raw.GetBuffer(), (int)raw.Length);
                if (raw.Length > 1 * 1024 * 1024) return false; // guard against a runaway/garbage header
            }

            var headerBytes = raw.GetBuffer();
            // Request lines and header names/values are always ASCII-safe per the HTTP spec.
            var headerText = Encoding.ASCII.GetString(headerBytes, 0, headerEnd);
            var lines = headerText.Split(new[] { "\r\n" }, StringSplitOptions.None);
            var requestParts = (lines.Length > 0 ? lines[0] : "").Split(' ');
            method = requestParts.Length > 0 ? requestParts[0] : "";
            path = requestParts.Length > 1 ? requestParts[1].Split('?')[0] : "/";

            var contentLength = 0;
            foreach (var line in lines)
            {
                if (line.StartsWith("Content-Length:", StringComparison.OrdinalIgnoreCase))
                {
                    int.TryParse(line.Substring("Content-Length:".Length).Trim(), out contentLength);
                }
            }
            if (contentLength <= 0)
            {
                bodyBytes = new byte[0];
                return true;
            }

            var bodyStart = headerEnd + 4; // skip the blank line's \r\n\r\n
            var alreadyBuffered = (int)raw.Length - bodyStart;
            var body = new MemoryStream(contentLength);
            if (alreadyBuffered > 0)
            {
                body.Write(headerBytes, bodyStart, Math.Min(alreadyBuffered, contentLength));
            }
            while (body.Length < contentLength)
            {
                var toRead = Math.Min(chunk.Length, contentLength - (int)body.Length);
                var read = stream.Read(chunk, 0, toRead);
                if (read <= 0) break;
                body.Write(chunk, 0, read);
            }
            bodyBytes = body.ToArray();
            return true;
        }

        private static int FindHeaderEnd(byte[] buffer, int length)
        {
            for (var i = 0; i + 3 < length; i++)
            {
                if (buffer[i] == (byte)'\r' && buffer[i + 1] == (byte)'\n' && buffer[i + 2] == (byte)'\r' && buffer[i + 3] == (byte)'\n')
                    return i;
            }
            return -1;
        }

        private Dictionary<string, object> SnapshotPayload()
        {
            return new Dictionary<string, object>
            {
                { "ok", true },
                { "app", "SchoolDom Admin Sync Win7" },
                { "school", SchoolPayload() },
                { "port", Port },
                { "addresses", LocalAddresses() },
                { "urls", LocalUrls() },
                { "running", _running },
                { "exams", _store.State.Exams.Count },
                { "students", _store.State.Students.Count },
                { "updated_at", JsonUtil.IsoNow() },
            };
        }

        // Login never starts a session by itself, even when exactly one exam matches the
        // PIN - the student always sees the Available Exams screen first and explicitly
        // picks "Start Exam" (POST /api/start-session), which is what actually creates or
        // resumes the session. This used to auto-call StartSession here for the
        // single-match case, silently creating exam state before the student had chosen
        // anything.
        private Dictionary<string, object> Login(string bodyText)
        {
            var body = JsonUtil.DeserializeObject(bodyText);
            var studentId = JsonUtil.Text(body.ContainsKey("studentId") ? body["studentId"] : body.ContainsKey("student_id") ? body["student_id"] : "").Trim();
            var pin = JsonUtil.Text(body.ContainsKey("pin") ? body["pin"] : "").Trim();
            var pinHash = JsonUtil.Sha256(pin);
            var student = _store.State.Students.FirstOrDefault(item => string.Equals(item.StudentId, studentId, StringComparison.OrdinalIgnoreCase));
            if (student == null) return new Dictionary<string, object> { { "success", false }, { "message", "Student ID was not found on the admin LAN server." } };
            if (!student.IsActive) return new Dictionary<string, object> { { "success", false }, { "message", "Your student account is inactive. Please contact your school administrator to renew your activation token." } };
            var matchingExams = _store.State.Exams.Where(item => string.Equals(item.PinHash, pinHash, StringComparison.OrdinalIgnoreCase)).ToList();
            if (!matchingExams.Any()) return new Dictionary<string, object> { { "success", false }, { "message", "Invalid exam PIN." } };

            var availableExams = matchingExams.Where(exam => IsExamAvailableToStudent(student, exam)).ToList();
            if (!availableExams.Any())
            {
                return new Dictionary<string, object> { { "success", false }, { "message", "No available exam matches this PIN - it may have expired or already been submitted." } };
            }
            return new Dictionary<string, object>
            {
                { "success", true },
                { "student", student },
                { "exams", availableExams.Select(exam => ExamChoicePayload(student, exam)).ToList() }
            };
        }

        // Already-submitted exams are never offered again (retaking requires an admin to
        // delete the result first, same rule StartSession already enforces). An exam whose
        // window has closed is still offered if the student already has an in-progress
        // session for it, so they can get back in and finish/submit; it's only hidden from
        // students who never started it.
        private bool IsExamAvailableToStudent(StudentRecord student, ExamRecord exam)
        {
            var session = FindSessionFor(student, exam);
            if (session != null && session.Status == "submitted") return false;
            if (session != null) return true;
            return !IsExamExpired(exam);
        }

        private static bool IsExamExpired(ExamRecord exam)
        {
            if (string.IsNullOrWhiteSpace(exam.EndsAt)) return false;
            DateTime ends;
            return DateTime.TryParse(exam.EndsAt, null, System.Globalization.DateTimeStyles.RoundtripKind, out ends)
                && DateTime.UtcNow > ends.ToUniversalTime();
        }

        private SessionRecord FindSessionFor(StudentRecord student, ExamRecord exam)
        {
            return _store.State.Sessions.FirstOrDefault(item => item.ExamId == exam.Id && string.Equals(item.StudentId, student.StudentId, StringComparison.OrdinalIgnoreCase));
        }

        private Dictionary<string, object> ExamChoicePayload(StudentRecord student, ExamRecord exam)
        {
            var payload = PublicExam(exam);
            var session = FindSessionFor(student, exam);
            payload["status"] = session != null && session.Status != "submitted" ? "In Progress" : "Not Started";
            return payload;
        }

        private Dictionary<string, object> StartSession(string bodyText)
        {
            var body = JsonUtil.DeserializeObject(bodyText);
            var studentId = JsonUtil.Text(body.ContainsKey("studentId") ? body["studentId"] : body.ContainsKey("student_id") ? body["student_id"] : "").Trim();
            var examId = JsonUtil.Text(body.ContainsKey("examId") ? body["examId"] : body.ContainsKey("exam_id") ? body["exam_id"] : "").Trim();
            var student = _store.State.Students.FirstOrDefault(item => string.Equals(item.StudentId, studentId, StringComparison.OrdinalIgnoreCase));
            if (student == null) return new Dictionary<string, object> { { "success", false }, { "message", "Student ID was not found on the admin LAN server." } };
            var exam = _store.State.Exams.FirstOrDefault(item => item.Id == examId);
            if (exam == null) return new Dictionary<string, object> { { "success", false }, { "message", "Exam was not found on the admin LAN server." } };
            return StartSession(student, exam);
        }

        private Dictionary<string, object> StartSession(StudentRecord student, ExamRecord exam)
        {
            var session = _store.State.Sessions.FirstOrDefault(item => item.ExamId == exam.Id && string.Equals(item.StudentId, student.StudentId, StringComparison.OrdinalIgnoreCase));
            if (session != null && session.Status == "submitted")
            {
                return new Dictionary<string, object> { { "success", false }, { "message", "This result has already been submitted. Ask the admin to delete the result before retaking." } };
            }
            if (session == null)
            {
                var started = DateTime.UtcNow;
                session = new SessionRecord
                {
                    Id = "lan_session_" + Guid.NewGuid().ToString("N"),
                    ExamId = exam.Id,
                    StudentId = student.StudentId,
                    StudentName = student.FullName,
                    Status = "in_progress",
                    StartedAt = started.ToString("o"),
                    EndsAt = started.AddSeconds(Math.Max(60, exam.DurationSeconds)).ToString("o"),
                    SyncStatus = "pending"
                };
                session.AuditLogs.Add(new ActivityLogRecord { Type = "session_started", Message = "Student started exam on LAN.", CreatedAt = JsonUtil.IsoNow() });
                _store.State.Sessions.Add(session);
                _store.Save();
            }
            else if (string.IsNullOrWhiteSpace(session.StudentName) || string.Equals(session.StudentName, session.StudentId, StringComparison.OrdinalIgnoreCase))
            {
                session.StudentName = student.FullName;
                _store.Save();
            }
            var result = new Dictionary<string, object> { { "success", true }, { "student", student }, { "exam", PublicExam(exam) }, { "session", session } };
            AddTimerFields(result, session);
            return result;
        }

        private Dictionary<string, object> SaveAnswers(string sessionId, string bodyText)
        {
            var session = FindSession(sessionId);
            if (session == null) return new Dictionary<string, object> { { "success", false }, { "message", "Session not found." } };
            if (session.Status == "submitted") return new Dictionary<string, object> { { "success", true }, { "session", session } };
            if (IsSessionExpired(session))
            {
                return new Dictionary<string, object> { { "success", false }, { "message", "Exam time has expired." } };
            }
            var body = JsonUtil.DeserializeObject(bodyText);
            session.Answers = body.ContainsKey("answers") ? NormalizeAnswers(body["answers"]) : session.Answers;
            _store.Save();
            var result = new Dictionary<string, object> { { "success", true }, { "session", session } };
            AddTimerFields(result, session);
            return result;
        }

        private Dictionary<string, object> SubmitSession(string sessionId, string bodyText)
        {
            var session = FindSession(sessionId);
            if (session == null) return new Dictionary<string, object> { { "success", false }, { "message", "Session not found." } };
            var body = JsonUtil.DeserializeObject(bodyText);
            // Accept final answers even if time just expired (grace: save whatever they have)
            if (body.ContainsKey("answers")) session.Answers = NormalizeAnswers(body["answers"]);
            session.Status = "submitted";
            session.SubmittedAt = JsonUtil.IsoNow();
            var reason = IsSessionExpired(session) ? "Time expired — auto-submitted on LAN." : "Student submitted exam on LAN.";
            session.AuditLogs.Add(new ActivityLogRecord { Type = "session_submitted", Message = reason, CreatedAt = JsonUtil.IsoNow() });
            _store.Save();
            var submitResult = new Dictionary<string, object> { { "success", true }, { "session", session } };
            AddTimerFields(submitResult, session);
            return submitResult;
        }

        private static bool IsSessionExpired(SessionRecord session)
        {
            return RemainingSeconds(session) <= 0 && !string.IsNullOrWhiteSpace(session.EndsAt);
        }

        // This LAN admin machine's clock is the single source of truth for every session's
        // countdown - EndsAt was computed from it in the first place. Every response that
        // carries a session also carries the remaining seconds computed right here, so student
        // stations never need to compare EndsAt against their OWN clock (which may be minutes,
        // hours, or a whole timezone off from the admin PC in an offline exam hall).
        private static int RemainingSeconds(SessionRecord session)
        {
            if (session == null || string.IsNullOrWhiteSpace(session.EndsAt)) return 0;
            DateTime ends;
            if (!DateTime.TryParse(session.EndsAt, null, System.Globalization.DateTimeStyles.RoundtripKind, out ends)) return 0;
            var remaining = (ends.ToUniversalTime() - DateTime.UtcNow).TotalSeconds;
            return remaining > 0 ? (int)Math.Ceiling(remaining) : 0;
        }

        private static void AddTimerFields(Dictionary<string, object> response, SessionRecord session)
        {
            if (response == null || session == null) return;
            var remaining = RemainingSeconds(session);
            response["time_remaining_seconds"] = remaining;
            response["expired"] = remaining <= 0;
            response["server_time"] = JsonUtil.IsoNow();
        }

        private Dictionary<string, object> BeginExam(string sessionId)
        {
            var session = FindSession(sessionId);
            if (session == null) return new Dictionary<string, object> { { "success", false }, { "message", "Session not found." } };
            if (session.Status == "submitted") return new Dictionary<string, object> { { "success", false }, { "message", "This exam has already been submitted." } };
            var exam = _store.State.Exams.FirstOrDefault(item => item.Id == session.ExamId);
            if (exam == null) return new Dictionary<string, object> { { "success", false }, { "message", "Exam record not found." } };
            var began = DateTime.UtcNow;
            session.ExamBeganAt = began.ToString("o");
            session.EndsAt = began.AddSeconds(Math.Max(60, exam.DurationSeconds)).ToString("o");
            session.AuditLogs.Add(new ActivityLogRecord { Type = "exam_began", Message = "Student entered exam mode on LAN.", CreatedAt = JsonUtil.IsoNow() });
            _store.Save();
            var beginResult = new Dictionary<string, object> { { "success", true }, { "session", session } };
            AddTimerFields(beginResult, session);
            return beginResult;
        }

        private Dictionary<string, object> LogFocusLoss(string sessionId, string bodyText)
        {
            var session = FindSession(sessionId);
            if (session == null) return new Dictionary<string, object> { { "success", false }, { "message", "Session not found." } };
            session.FocusLossCount += 1;
            session.AuditLogs.Add(new ActivityLogRecord { Type = "focus_loss", Message = "Student left CBT window.", CreatedAt = JsonUtil.IsoNow() });
            _store.Save();
            return new Dictionary<string, object> { { "success", true }, { "session", session } };
        }

        private SessionRecord FindSession(string sessionId)
        {
            return _store.State.Sessions.FirstOrDefault(item => item.Id == sessionId);
        }

        private static Dictionary<string, object> NormalizeAnswers(object value)
        {
            var raw = value as Dictionary<string, object>;
            return raw ?? new Dictionary<string, object>();
        }

        private static Dictionary<string, object> PublicExam(ExamRecord exam)
        {
            var questions = exam.Questions ?? new List<QuestionRecord>();
            return new Dictionary<string, object>
            {
                { "id", exam.Id },
                { "title", exam.Title },
                { "subject", exam.Subject },
                { "class_name", exam.ClassName },
                { "duration_seconds", exam.DurationSeconds },
                { "instructions", exam.Instructions },
                { "question_count", questions.Count },
                { "exam_type", ExamTypeLabel(questions) },
            };
        }

        // Derived locally from the already-synced question list rather than a separate
        // exam_format field from the backend, so this needed no changes to the sync
        // payload/pipeline - it's read-only display metadata, not new data flowing through.
        private static string ExamTypeLabel(List<QuestionRecord> questions)
        {
            var hasObjective = questions.Any(q => !PackageService.IsWrittenType(q.Type));
            var hasWritten = questions.Any(q => PackageService.IsWrittenType(q.Type));
            if (hasObjective && hasWritten) return "Mixed (Objective + Theory)";
            if (hasWritten) return "Theory";
            return "Objective (MCQ)";
        }

        private Dictionary<string, object> PackagePayload()
        {
            return new Dictionary<string, object>
            {
                { "success", true },
                { "package_type", "schooldom_cbt_exam_package" },
                { "package_version", 1 },
                { "package_id", _store.State.ActivePackageId ?? "" },
                { "generated_at", _store.State.PackageGeneratedAt ?? "" },
                { "school", SchoolPayload() },
                { "exams", _store.State.Exams },
                { "students", _store.State.Students },
            };
        }

        private Dictionary<string, object> SchoolPayload()
        {
            return new Dictionary<string, object>
            {
                { "name", DisplaySchoolName() },
                { "school_code", _store.State.SchoolCode ?? "" },
            };
        }

        private string DisplaySchoolName()
        {
            return string.IsNullOrWhiteSpace(_store.State.SchoolName) ? "SchoolDom" : _store.State.SchoolName;
        }

        private static void WriteJson(NetworkStream stream, int statusCode, object payload)
        {
            var body = Encoding.UTF8.GetBytes(JsonUtil.Serialize(payload));
            var statusText = statusCode == 200 ? "OK" : statusCode == 404 ? "Not Found" : "Error";
            var header =
                "HTTP/1.1 " + statusCode + " " + statusText + "\r\n" +
                "Content-Type: application/json; charset=utf-8\r\n" +
                "Access-Control-Allow-Origin: *\r\n" +
                "Access-Control-Allow-Headers: Content-Type\r\n" +
                "Access-Control-Allow-Methods: GET,POST,OPTIONS\r\n" +
                "Content-Length: " + body.Length + "\r\n" +
                "Connection: close\r\n\r\n";
            var headerBytes = Encoding.ASCII.GetBytes(header);
            stream.Write(headerBytes, 0, headerBytes.Length);
            stream.Write(body, 0, body.Length);
        }

        private static List<string> LocalAddresses()
        {
            var addresses = new List<string>();
            foreach (var adapter in NetworkInterface.GetAllNetworkInterfaces())
            {
                if (adapter.OperationalStatus != OperationalStatus.Up) continue;
                foreach (var unicast in adapter.GetIPProperties().UnicastAddresses)
                {
                    if (unicast.Address.AddressFamily != AddressFamily.InterNetwork) continue;
                    if (IPAddress.IsLoopback(unicast.Address)) continue;
                    addresses.Add(unicast.Address.ToString());
                }
            }
            return addresses.Distinct().ToList();
        }
    }
}
