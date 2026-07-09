using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.IO.Packaging;
using System.Linq;
using System.Net;
using System.Text;
using System.Text.RegularExpressions;

namespace SchoolDom.Cbt.Win7
{
    public class PackageService
    {
        private readonly LocalStore _store;

        public PackageService(LocalStore store)
        {
            _store = store;
        }

        public string ImportPackage(string path, string fallbackPin)
        {
            return ImportPackageJson(ReadTextSmart(path), fallbackPin);
        }

        public string ImportExamFile(string path, string fallbackPin)
        {
            var extension = Path.GetExtension(path ?? "").ToLowerInvariant();
            if (extension == ".json")
            {
                var json = ReadTextSmart(path);
                var root = JsonUtil.DeserializeObject(json);
                if (root.ContainsKey("package_type") || root.ContainsKey("exams") || root.ContainsKey("published_exams"))
                {
                    return ImportPackageJson(json, fallbackPin);
                }
                var exam = ExamFromJson(root, Path.GetFileNameWithoutExtension(path), fallbackPin);
                AddExam(exam);
                return "Imported exam: " + exam.Title + ".";
            }

            var text = extension == ".docx" ? ReadDocxText(path) : ReadTextSmart(path);
            var imported = extension == ".csv"
                ? ExamFromCsv(text, Path.GetFileNameWithoutExtension(path), fallbackPin)
                : ExamFromText(text, Path.GetFileNameWithoutExtension(path), fallbackPin);
            AddExam(imported);
            return "Imported exam: " + imported.Title + ".";
        }

        public string ImportPackageJson(string json, string fallbackPin)
        {
            var root = JsonUtil.DeserializeObject(json);
            var exams = ToList(root.ContainsKey("exams") ? root["exams"] : null);
            if (exams.Count == 0 && root.ContainsKey("published_exams")) exams = ToList(root["published_exams"]);
            var students = ToList(root.ContainsKey("students") ? root["students"] : null);
            var fallbackHash = string.IsNullOrWhiteSpace(fallbackPin) ? "" : JsonUtil.Sha256(fallbackPin.Trim());
            _store.State.Exams.Clear();
            _store.State.Students.Clear();
            _store.State.ActivePackageId = GetText(root, "package_id", JsonUtil.Sha256(json + JsonUtil.IsoNow()));
            _store.State.PackageGeneratedAt = GetText(root, "generated_at", "");
            _store.State.PackageLockedAt = JsonUtil.IsoNow();
            var school = root.ContainsKey("school") ? root["school"] as Dictionary<string, object> : null;
            if (school != null)
            {
                _store.State.SchoolName = FirstText(school, "name", "school_name");
                _store.State.SchoolCode = FirstText(school, "school_code", "code");
            }

            foreach (var studentObj in students)
            {
                var row = studentObj as Dictionary<string, object>;
                if (row == null) continue;
                var studentId = FirstText(row, "student_id", "admission_number", "id").Trim();
                if (studentId.Length == 0) continue;
                _store.State.Students.Add(new StudentRecord
                {
                    Id = FirstText(row, "id", "student_id"),
                    StudentId = studentId,
                    FullName = StudentNameFromRow(row, studentId),
                    ClassName = FirstText(row, "class_name", "class_label"),
                    ProfilePicture = FirstText(row, "profile_picture", "profile_picture_url", "photo", "photo_url"),
                    ProfilePictureData = FirstText(row, "profile_picture_data", "photo_data")
                });
                var cached = _store.State.Students[_store.State.Students.Count - 1];
                if (string.IsNullOrWhiteSpace(cached.ProfilePictureData))
                {
                    cached.ProfilePictureData = DownloadImageDataUrl(cached.ProfilePicture);
                }
            }

            foreach (var examObj in exams)
            {
                var row = examObj as Dictionary<string, object>;
                if (row == null) continue;
                var exam = new ExamRecord
                {
                    Id = FirstText(row, "id", "exam_id"),
                    Title = FirstText(row, "title", "name"),
                    Subject = FirstText(row, "subject", "subject_name"),
                    ClassName = FirstText(row, "class_name", "class_label"),
                    DurationSeconds = JsonUtil.Int(row.ContainsKey("duration_seconds") ? row["duration_seconds"] : null, JsonUtil.Int(row.ContainsKey("duration_minutes") ? row["duration_minutes"] : null, 60) * 60),
                    StartsAt = FirstText(row, "start_date", "starts_at"),
                    EndsAt = FirstText(row, "end_date", "ends_at"),
                    Instructions = FirstText(row, "instructions"),
                    PinHash = FirstText(row, "offline_pin_hash", "pin_sha256")
                };
                if (string.IsNullOrWhiteSpace(exam.PinHash)) exam.PinHash = fallbackHash;
                foreach (var questionObj in ToList(row.ContainsKey("questions") ? row["questions"] : null))
                {
                    var q = questionObj as Dictionary<string, object>;
                    if (q == null) continue;
                    exam.Questions.Add(ParseQuestion(q));
                }
                if (exam.Id.Length > 0 && exam.Questions.Count > 0) _store.State.Exams.Add(exam);
            }

            _store.Save();
            if (_store.State.Exams.Count == 0 && _store.State.Students.Count == 0)
            {
                return "Signed in. No published exams or students were available to sync yet.";
            }
            if (_store.State.Exams.Count == 0)
            {
                return "Signed in and synced " + _store.State.Students.Count + " student(s). No published exams are available yet.";
            }
            return "Imported " + _store.State.Exams.Count + " exam(s) and " + _store.State.Students.Count + " student(s).";
        }

        public string ExportBroadsheet(string path)
        {
            var lines = new List<string>();
            var headers = new List<string> { "Student ID", "Full Name", "Class" };
            headers.AddRange(_store.State.Exams.Select(e => e.Title + " Score"));
            lines.Add(Csv(headers));

            foreach (var student in _store.State.Students.OrderBy(s => s.FullName))
            {
                var row = new List<string> { student.StudentId, student.FullName, student.ClassName };
                foreach (var exam in _store.State.Exams)
                {
                    var session = _store.State.Sessions.FirstOrDefault(s =>
                        s.ExamId == exam.Id &&
                        string.Equals(s.StudentId, student.StudentId, StringComparison.OrdinalIgnoreCase));
                    if (session == null) row.Add("Not submitted");
                    else if (session.Status != "submitted") row.Add("In progress");
                    else row.Add(ComputeScore(session, exam).Display);
                }
                lines.Add(Csv(row));
            }

            File.WriteAllLines(path, lines.ToArray());
            return "Broadsheet exported for " + _store.State.Students.Count + " student(s).";
        }

        public void SaveExam(ExamRecord exam)
        {
            var existing = _store.State.Exams.FirstOrDefault(e => e.Id == exam.Id);
            if (existing == null) return;
            existing.Title = exam.Title;
            existing.Subject = exam.Subject;
            existing.ClassName = exam.ClassName;
            existing.DurationSeconds = exam.DurationSeconds;
            existing.StartsAt = exam.StartsAt;
            existing.EndsAt = exam.EndsAt;
            existing.Instructions = exam.Instructions;
            existing.PinHash = exam.PinHash;
            existing.Questions = exam.Questions ?? new List<QuestionRecord>();
            _store.Save();
        }

        public void AddExam(ExamRecord exam)
        {
            if (exam == null) return;
            if (string.IsNullOrWhiteSpace(exam.Id)) exam.Id = "local_exam_" + Guid.NewGuid().ToString("N");
            if (exam.Questions == null) exam.Questions = new List<QuestionRecord>();
            _store.State.Exams.RemoveAll(e => e.Id == exam.Id);
            _store.State.Exams.Add(exam);
            _store.Save();
        }

        public string DeleteSession(string sessionId)
        {
            var session = _store.State.Sessions.FirstOrDefault(s => s.Id == sessionId);
            if (session == null) return "Result was already removed locally.";
            _store.State.Sessions.Remove(session);
            _store.Save();
            return "Local result removed. Student can retake this exam on the LAN app.";
        }

        private static string Csv(IEnumerable<string> values)
        {
            return string.Join(",", values.Select(value => "\"" + (value ?? "").Replace("\"", "\"\"") + "\""));
        }

        public string ExportResults(string path)
        {
            var json = ExportResultsJson(markExported: true);
            File.WriteAllText(path, json);
            return "Exported " + _lastExportCount + " submitted result(s).";
        }

        private int _lastExportCount;

        public string ExportResultsJson(bool markExported)
        {
            var submitted = _store.State.Sessions.Where(s => s.Status == "submitted").ToList();
            var results = new List<object>();
            foreach (var session in submitted)
            {
                var envelope = BuildEnvelope(session);
                results.Add(new Dictionary<string, object>
                {
                    { "package_item_id", "sync_" + session.Id },
                    { "entity_id", session.Id },
                    { "attempts", 0 },
                    { "last_error", "" },
                    { "created_at", session.SubmittedAt ?? session.StartedAt },
                    { "payload", envelope["payload"] },
                    { "sync_envelope", envelope }
                });
                if (markExported) session.SyncStatus = "exported";
            }

            var package = new Dictionary<string, object>
            {
                { "package_type", "schooldom_cbt_results" },
                { "package_version", 1 },
                { "generated_at", JsonUtil.IsoNow() },
                { "results", results },
                { "summary", new Dictionary<string, object>
                    {
                        { "pending_results", results.Count },
                        { "package_id", _store.State.ActivePackageId ?? "" },
                        { "device_id", _store.State.DeviceId ?? "" }
                    }
                }
            };

            _lastExportCount = results.Count;
            if (markExported) _store.Save();
            return JsonUtil.Serialize(package);
        }

        public void MarkSubmittedResultsSynced()
        {
            foreach (var session in _store.State.Sessions.Where(s => s.Status == "submitted"))
            {
                session.SyncStatus = "synced";
            }
            _store.Save();
        }

        public static bool IsWrittenType(string type)
        {
            var value = (type ?? "").ToLowerInvariant();
            return value == "essay" || value == "theory" || value == "written";
        }

        public static string FormatScoreNumber(double value)
        {
            return value == Math.Floor(value) ? ((int)value).ToString() : value.ToString("0.##");
        }

        // Computes a session's score: objective questions (mcq/true-false/fill-blank) are
        // auto-graded by comparing the student's answer to CorrectAnswer; written/essay
        // questions require an admin-awarded mark stored in session.ManualScores.
        public static ExamScore ComputeScore(SessionRecord session, ExamRecord exam)
        {
            var result = new ExamScore();
            if (exam == null || exam.Questions == null) return result;
            var answers = (session != null ? session.Answers : null) ?? new Dictionary<string, object>();
            var manual = (session != null ? session.ManualScores : null) ?? new Dictionary<string, double>();
            foreach (var q in exam.Questions)
            {
                var points = q.Points <= 0 ? 1 : q.Points;
                result.MaxScore += points;

                if (IsWrittenType(q.Type))
                {
                    double awarded;
                    if (manual.TryGetValue(q.Id, out awarded))
                    {
                        result.Score += Math.Max(0, Math.Min(awarded, points));
                    }
                    else
                    {
                        result.PendingManual++;
                    }
                    continue;
                }

                object raw;
                if (!answers.TryGetValue(q.Id, out raw)) continue;
                var answerText = JsonUtil.Text(raw);
                var selected = answerText;
                int optionIndex;
                if (q.Options != null && q.Options.Count > 0 && int.TryParse(answerText, out optionIndex) &&
                    optionIndex >= 0 && optionIndex < q.Options.Count)
                {
                    selected = q.Options[optionIndex];
                }
                if (!string.IsNullOrWhiteSpace(q.CorrectAnswer) &&
                    string.Equals((selected ?? "").Trim(), q.CorrectAnswer.Trim(), StringComparison.OrdinalIgnoreCase))
                {
                    result.Score += points;
                }
            }
            return result;
        }

        private Dictionary<string, object> BuildEnvelope(SessionRecord session)
        {
            var exam = _store.State.Exams.FirstOrDefault(e => e.Id == session.ExamId);
            var score = ComputeScore(session, exam);
            var payload = new Dictionary<string, object>
            {
                { "session_id", session.Id },
                { "exam_id", session.ExamId },
                { "student_id", session.StudentId },
                { "student_name", session.StudentName ?? "" },
                { "answers", session.Answers },
                { "started_at", session.StartedAt },
                { "submitted_at", session.SubmittedAt },
                { "focus_loss_count", session.FocusLossCount },
                { "malpractice_log", new object[0] },
                { "audit_logs", session.AuditLogs ?? new List<ActivityLogRecord>() },
                { "cause", "student_submit" },
                { "score", score.Score },
                { "max_score", score.MaxScore },
                { "pending_manual_grading", score.PendingManual },
                { "manual_scores", session.ManualScores ?? new Dictionary<string, double>() }
            };
            var envelope = new Dictionary<string, object>
            {
                { "envelope_type", "schooldom_cbt_result_sync" },
                { "envelope_version", 1 },
                { "sync_id", "sync_" + session.Id },
                { "entity_type", "result" },
                { "entity_id", session.Id },
                { "device_id", _store.State.DeviceId ?? "" },
                { "package_id", _store.State.ActivePackageId ?? "" },
                { "package_locked_at", _store.State.PackageLockedAt ?? "" },
                { "created_at", session.SubmittedAt ?? JsonUtil.IsoNow() },
                { "attempts", 0 },
                { "payload", payload }
            };
            envelope["checksum"] = JsonUtil.Sha256(JsonUtil.Serialize(new Dictionary<string, object>
            {
                { "sync_id", envelope["sync_id"] },
                { "device_id", envelope["device_id"] },
                { "package_id", envelope["package_id"] },
                { "payload", payload }
            }));
            return envelope;
        }

        private static QuestionRecord ParseQuestion(Dictionary<string, object> q)
        {
            var question = new QuestionRecord
            {
                Id = FirstText(q, "id"),
                Text = FirstText(q, "text"),
                Type = FirstText(q, "type", "question_type"),
                Points = JsonUtil.Double(q.ContainsKey("points") ? q["points"] : null, JsonUtil.Double(q.ContainsKey("marks") ? q["marks"] : null, 1)),
                CorrectAnswer = FirstText(q, "correct_answer")
            };
            foreach (var item in ToList(q.ContainsKey("options") ? q["options"] : null))
            {
                if (item is Dictionary<string, object>)
                {
                    var opt = (Dictionary<string, object>)item;
                    question.Options.Add(FirstText(opt, "text", "label", "value"));
                }
                else
                {
                    question.Options.Add(JsonUtil.Text(item));
                }
            }
            if (question.Type == "true_false" && question.Options.Count == 0)
            {
                question.Options.Add("True");
                question.Options.Add("False");
            }
            var group = q.ContainsKey("group") ? q["group"] as Dictionary<string, object> : null;
            if (group != null)
            {
                question.Group = new QuestionGroupRecord
                {
                    Title = FirstText(group, "title"),
                    PassageText = FirstText(group, "passage_text")
                };
            }
            return question;
        }

        private static ExamRecord ExamFromJson(Dictionary<string, object> root, string fallbackTitle, string fallbackPin)
        {
            var exam = new ExamRecord
            {
                Id = FirstText(root, "id", "exam_id"),
                Title = FirstText(root, "title", "name"),
                Subject = FirstText(root, "subject", "subject_name"),
                ClassName = FirstText(root, "class_name", "class_label"),
                DurationSeconds = JsonUtil.Int(root.ContainsKey("duration_seconds") ? root["duration_seconds"] : null, JsonUtil.Int(root.ContainsKey("duration_minutes") ? root["duration_minutes"] : null, 60) * 60),
                StartsAt = JsonUtil.IsoNow(),
                EndsAt = DateTime.UtcNow.AddDays(30).ToString("o"),
                Instructions = FirstText(root, "instructions"),
                PinHash = FirstText(root, "offline_pin_hash", "pin_sha256")
            };
            if (string.IsNullOrWhiteSpace(exam.Id)) exam.Id = "imported_exam_" + Guid.NewGuid().ToString("N");
            if (string.IsNullOrWhiteSpace(exam.Title)) exam.Title = fallbackTitle;
            if (string.IsNullOrWhiteSpace(exam.PinHash) && !string.IsNullOrWhiteSpace(fallbackPin)) exam.PinHash = JsonUtil.Sha256(fallbackPin.Trim());
            foreach (var questionObj in ToList(root.ContainsKey("questions") ? root["questions"] : null))
            {
                var q = questionObj as Dictionary<string, object>;
                if (q != null) exam.Questions.Add(ParseQuestion(q));
            }
            ValidateImportedExam(exam);
            return exam;
        }

        private static ExamRecord ExamFromCsv(string text, string fallbackTitle, string fallbackPin)
        {
            var exam = NewImportedExam(fallbackTitle, fallbackPin);
            var rows = Regex.Split(text ?? "", "\r\n|\n|\r").Where(line => !string.IsNullOrWhiteSpace(line)).ToList();
            if (rows.Count == 0) throw new InvalidOperationException("This CSV file is empty.");
            var start = LooksLikeHeader(rows[0]) ? 1 : 0;
            for (var i = start; i < rows.Count; i++)
            {
                var cols = SplitCsvLine(rows[i]);
                if (cols.Count < 3) continue;
                var options = cols.Skip(1).Take(Math.Min(4, cols.Count - 2)).Where(x => !string.IsNullOrWhiteSpace(x)).ToList();
                var answer = cols.Count >= 6 ? cols[5] : cols.Last();
                var marksText = cols.Count >= 7 ? cols[6] : "";
                exam.Questions.Add(BuildQuestion(cols[0], options, answer, marksText));
            }
            ValidateImportedExam(exam);
            return exam;
        }

        private static ExamRecord ExamFromText(string text, string fallbackTitle, string fallbackPin)
        {
            var exam = NewImportedExam(fallbackTitle, fallbackPin);
            var currentText = "";
            var options = new List<string>();
            var answer = "";
            var marks = "1";
            Action flush = () =>
            {
                if (string.IsNullOrWhiteSpace(currentText)) return;
                exam.Questions.Add(BuildQuestion(currentText, options, answer, marks));
                currentText = "";
                options = new List<string>();
                answer = "";
                marks = "1";
            };

            foreach (var raw in Regex.Split(text ?? "", "\r\n|\n|\r"))
            {
                var line = NormalizeWhitespace(raw);
                if (line.Length == 0) continue;
                if (line.StartsWith("Title:", StringComparison.OrdinalIgnoreCase)) { exam.Title = line.Substring(6).Trim(); continue; }
                if (line.StartsWith("Subject:", StringComparison.OrdinalIgnoreCase)) { exam.Subject = line.Substring(8).Trim(); continue; }
                if (line.StartsWith("Class:", StringComparison.OrdinalIgnoreCase)) { exam.ClassName = line.Substring(6).Trim(); continue; }
                if (line.StartsWith("Duration:", StringComparison.OrdinalIgnoreCase))
                {
                    var value = Regex.Match(line, @"\d+").Value;
                    int minutes;
                    if (int.TryParse(value, out minutes) && minutes > 0) exam.DurationSeconds = minutes * 60;
                    continue;
                }
                if (line.StartsWith("Instructions:", StringComparison.OrdinalIgnoreCase)) { exam.Instructions = line.Substring(13).Trim(); continue; }
                if (line.StartsWith("PIN:", StringComparison.OrdinalIgnoreCase)) { exam.PinHash = JsonUtil.Sha256(line.Substring(4).Trim()); continue; }

                var optionMatch = Regex.Match(line, @"^([A-Da-d])[\)\.\-:]\s*(.+)$");
                if (optionMatch.Success)
                {
                    options.Add(optionMatch.Groups[2].Value.Trim());
                    continue;
                }
                if (line.StartsWith("Answer:", StringComparison.OrdinalIgnoreCase) || line.StartsWith("Correct:", StringComparison.OrdinalIgnoreCase))
                {
                    answer = line.Substring(line.IndexOf(':') + 1).Trim();
                    continue;
                }
                if (line.StartsWith("Marks:", StringComparison.OrdinalIgnoreCase) || line.StartsWith("Mark:", StringComparison.OrdinalIgnoreCase) || line.StartsWith("Points:", StringComparison.OrdinalIgnoreCase))
                {
                    marks = line.Substring(line.IndexOf(':') + 1).Trim();
                    continue;
                }

                if (Regex.IsMatch(line, @"^(\d+[\)\.]|Q\d*[\)\.\-:]?)\s+", RegexOptions.IgnoreCase))
                {
                    flush();
                    currentText = Regex.Replace(line, @"^(\d+[\)\.]|Q\d*[\)\.\-:]?)\s+", "", RegexOptions.IgnoreCase).Trim();
                }
                else if (currentText.Length == 0)
                {
                    currentText = line;
                }
                else
                {
                    currentText += " " + line;
                }
            }
            flush();
            ValidateImportedExam(exam);
            return exam;
        }

        private static ExamRecord NewImportedExam(string fallbackTitle, string fallbackPin)
        {
            return new ExamRecord
            {
                Id = "imported_exam_" + Guid.NewGuid().ToString("N"),
                Title = string.IsNullOrWhiteSpace(fallbackTitle) ? "Imported Exam" : fallbackTitle,
                DurationSeconds = 3600,
                StartsAt = JsonUtil.IsoNow(),
                EndsAt = DateTime.UtcNow.AddDays(30).ToString("o"),
                PinHash = string.IsNullOrWhiteSpace(fallbackPin) ? "" : JsonUtil.Sha256(fallbackPin.Trim())
            };
        }

        private static QuestionRecord BuildQuestion(string text, List<string> options, string answer, string marksText)
        {
            double marks;
            if (!double.TryParse(Regex.Match(marksText ?? "", @"\d+(\.\d+)?").Value, out marks) || marks <= 0) marks = 1;
            var cleanOptions = (options ?? new List<string>()).Select(NormalizeWhitespace).Where(x => x.Length > 0).ToList();
            var correct = ResolveCorrectAnswer(cleanOptions, answer);
            return new QuestionRecord
            {
                Id = "imported_question_" + Guid.NewGuid().ToString("N"),
                Text = NormalizeWhitespace(text),
                Type = cleanOptions.Count > 0 ? "mcq" : "essay",
                Points = marks,
                CorrectAnswer = correct,
                Options = cleanOptions
            };
        }

        private static string ResolveCorrectAnswer(List<string> options, string answer)
        {
            var value = NormalizeWhitespace(answer);
            if (options == null || options.Count == 0) return value;
            var letter = value.Length > 0 ? char.ToUpperInvariant(value[0]) : '\0';
            if (letter >= 'A' && letter <= 'D')
            {
                var index = letter - 'A';
                if (index >= 0 && index < options.Count) return options[index];
            }
            var match = options.FirstOrDefault(o => string.Equals(o, value, StringComparison.OrdinalIgnoreCase));
            return string.IsNullOrWhiteSpace(match) ? options[0] : match;
        }

        private static void ValidateImportedExam(ExamRecord exam)
        {
            if (string.IsNullOrWhiteSpace(exam.Title)) exam.Title = "Imported Exam";
            if (exam.DurationSeconds <= 0) exam.DurationSeconds = 3600;
            if (exam.Questions == null || exam.Questions.Count == 0)
            {
                throw new InvalidOperationException("No questions were found. Use numbered questions and A-D options, or import a SchoolDom JSON package.");
            }
            foreach (var question in exam.Questions)
            {
                if (question.Options == null) question.Options = new List<string>();
                question.Text = NormalizeWhitespace(question.Text);
                if (string.IsNullOrWhiteSpace(question.Text)) question.Text = "Question";
                if (question.Points <= 0) question.Points = 1;
                if (question.Options.Count > 0 && string.IsNullOrWhiteSpace(question.CorrectAnswer)) question.CorrectAnswer = question.Options[0];
            }
        }

        private static string ReadDocxText(string path)
        {
            // System.IO.Compression.ZipFile requires .NET 4.5+.
            // System.IO.Packaging.Package (WindowsBase.dll) ships with Win7 and supports .NET 4.0.
            // A .docx is a valid OPC/ZIP package so Package.Open() reads it correctly.
            var partUri = new Uri("/word/document.xml", UriKind.Relative);
            using (var package = Package.Open(path, FileMode.Open, FileAccess.Read))
            {
                if (!package.PartExists(partUri))
                    throw new InvalidOperationException("Could not read the Word document body.");
                using (var stream = package.GetPart(partUri).GetStream())
                using (var reader = new StreamReader(stream, Encoding.UTF8))
                {
                    var xml = reader.ReadToEnd();
                    xml = Regex.Replace(xml, @"</w:p>", "\n", RegexOptions.IgnoreCase);
                    xml = Regex.Replace(xml, @"<[^>]+>", " ");
                    return DecodeXmlEntities(xml);
                }
            }
        }

        private static string ReadTextSmart(string path)
        {
            var bytes = File.ReadAllBytes(path);
            foreach (var encoding in new[] { new UTF8Encoding(false, true), Encoding.Unicode, Encoding.BigEndianUnicode, Encoding.Default })
            {
                try { return encoding.GetString(bytes); }
                catch (DecoderFallbackException) { }
            }
            return Encoding.UTF8.GetString(bytes);
        }

        private static string DecodeXmlEntities(string value)
        {
            return (value ?? "")
                .Replace("&lt;", "<")
                .Replace("&gt;", ">")
                .Replace("&amp;", "&")
                .Replace("&quot;", "\"")
                .Replace("&apos;", "'");
        }

        private static string NormalizeWhitespace(string value)
        {
            return Regex.Replace((value ?? "").Replace('\u00A0', ' '), @"\s+", " ").Trim();
        }

        private static bool LooksLikeHeader(string line)
        {
            var lower = (line ?? "").ToLowerInvariant();
            return lower.Contains("question") || lower.Contains("option") || lower.Contains("answer") || lower.Contains("mark");
        }

        private static List<string> SplitCsvLine(string line)
        {
            var values = new List<string>();
            var current = new StringBuilder();
            var quoted = false;
            for (var i = 0; i < (line ?? "").Length; i++)
            {
                var ch = line[i];
                if (ch == '"')
                {
                    if (quoted && i + 1 < line.Length && line[i + 1] == '"')
                    {
                        current.Append('"');
                        i++;
                    }
                    else quoted = !quoted;
                }
                else if (ch == ',' && !quoted)
                {
                    values.Add(current.ToString().Trim());
                    current.Length = 0;
                }
                else current.Append(ch);
            }
            values.Add(current.ToString().Trim());
            return values;
        }

        private static string DownloadImageDataUrl(string url)
        {
            if (string.IsNullOrWhiteSpace(url)) return "";
            if (url.StartsWith("data:image/", StringComparison.OrdinalIgnoreCase)) return url;
            if (!url.StartsWith("http://", StringComparison.OrdinalIgnoreCase) && !url.StartsWith("https://", StringComparison.OrdinalIgnoreCase)) return "";
            try
            {
                // Tls12 (3072) is not a named member in .NET 4.0 — use numeric cast
                try { ServicePointManager.SecurityProtocol = (SecurityProtocolType)3072; }
                catch { ServicePointManager.SecurityProtocol = SecurityProtocolType.Tls; }
                using (var client = new WebClient())
                {
                    client.Headers["User-Agent"] = "SchoolDom-Admin-Sync-Win7";
                    var bytes = client.DownloadData(url);
                    if (bytes == null || bytes.Length == 0 || bytes.Length > 512 * 1024) return "";
                    var lower = url.ToLowerInvariant();
                    var mime = lower.EndsWith(".png") ? "image/png" : lower.EndsWith(".gif") ? "image/gif" : "image/jpeg";
                    return "data:" + mime + ";base64," + Convert.ToBase64String(bytes);
                }
            }
            catch { return ""; }
        }

        private static string GetText(Dictionary<string, object> row, string key, string fallback)
        {
            return row.ContainsKey(key) ? JsonUtil.Text(row[key], fallback) : fallback;
        }

        private static string FirstText(Dictionary<string, object> row, params string[] keys)
        {
            foreach (var key in keys)
            {
                if (row.ContainsKey(key))
                {
                    var value = JsonUtil.Text(row[key]);
                    if (!string.IsNullOrWhiteSpace(value)) return value;
                }
            }
            return "";
        }

        private static string StudentNameFromRow(Dictionary<string, object> row, string studentId)
        {
            var name = FirstText(row, "full_name", "student_name", "name", "display_name");
            if (LooksLikeStudentId(name, studentId)) name = "";
            if (string.IsNullOrWhiteSpace(name))
            {
                name = (FirstText(row, "first_name", "firstname", "given_name") + " " + FirstText(row, "last_name", "lastname", "surname", "family_name")).Trim();
            }
            if (LooksLikeStudentId(name, studentId)) name = "";
            return string.IsNullOrWhiteSpace(name) ? studentId : name;
        }

        private static bool LooksLikeStudentId(string value, string studentId)
        {
            return !string.IsNullOrWhiteSpace(value) && string.Equals(value.Trim(), (studentId ?? "").Trim(), StringComparison.OrdinalIgnoreCase);
        }

        private static List<object> ToList(object value)
        {
            if (value == null) return new List<object>();
            var list = value as object[];
            if (list != null) return list.Cast<object>().ToList();
            var array = value as ArrayList;
            if (array != null) return array.Cast<object>().ToList();
            var enumerable = value as IEnumerable<object>;
            return enumerable != null ? enumerable.ToList() : new List<object>();
        }
    }

    public class ExamScore
    {
        public double Score { get; set; }
        public double MaxScore { get; set; }
        public int PendingManual { get; set; }

        public string Display
        {
            get
            {
                if (MaxScore <= 0) return "-";
                var text = PackageService.FormatScoreNumber(Score) + " / " + PackageService.FormatScoreNumber(MaxScore);
                if (PendingManual > 0) text += " (" + PendingManual + " ungraded)";
                return text;
            }
        }
    }
}
