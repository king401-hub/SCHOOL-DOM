using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;

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
            return ImportPackageJson(File.ReadAllText(path), fallbackPin);
        }

        public string ImportPackageJson(string json, string fallbackPin)
        {
            var root = JsonUtil.DeserializeObject(json);
            var exams = ToList(root.ContainsKey("exams") ? root["exams"] : null);
            if (exams.Count == 0 && root.ContainsKey("published_exams")) exams = ToList(root["published_exams"]);
            var students = ToList(root.ContainsKey("students") ? root["students"] : null);
            if (exams.Count == 0) throw new InvalidOperationException("Package has no exams.");
            if (students.Count == 0) throw new InvalidOperationException("Package has no students.");

            var fallbackHash = string.IsNullOrWhiteSpace(fallbackPin) ? "" : JsonUtil.Sha256(fallbackPin.Trim());
            _store.State.Exams.Clear();
            _store.State.Students.Clear();
            _store.State.Sessions.Clear();
            _store.State.ActivePackageId = GetText(root, "package_id", JsonUtil.Sha256(json + JsonUtil.IsoNow()));
            _store.State.PackageGeneratedAt = GetText(root, "generated_at", "");
            _store.State.PackageLockedAt = JsonUtil.IsoNow();

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
                    FullName = FirstText(row, "full_name", "name", "email"),
                    ClassName = FirstText(row, "class_name", "class_label")
                });
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
                if (string.IsNullOrWhiteSpace(exam.PinHash))
                {
                    throw new InvalidOperationException("This package does not include an offline PIN hash. Enter the published exam PIN during import.");
                }
                foreach (var questionObj in ToList(row.ContainsKey("questions") ? row["questions"] : null))
                {
                    var q = questionObj as Dictionary<string, object>;
                    if (q == null) continue;
                    exam.Questions.Add(ParseQuestion(q));
                }
                if (exam.Id.Length > 0 && exam.Questions.Count > 0) _store.State.Exams.Add(exam);
            }

            _store.Save();
            return "Imported " + _store.State.Exams.Count + " exam(s) and " + _store.State.Students.Count + " student(s).";
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

        private Dictionary<string, object> BuildEnvelope(SessionRecord session)
        {
            var payload = new Dictionary<string, object>
            {
                { "session_id", session.Id },
                { "exam_id", session.ExamId },
                { "student_id", session.StudentId },
                { "answers", session.Answers },
                { "started_at", session.StartedAt },
                { "submitted_at", session.SubmittedAt },
                { "focus_loss_count", session.FocusLossCount },
                { "malpractice_log", new object[0] },
                { "audit_logs", session.AuditLogs ?? new List<ActivityLogRecord>() },
                { "cause", "student_submit" }
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
                Points = JsonUtil.Double(q.ContainsKey("points") ? q["points"] : null, JsonUtil.Double(q.ContainsKey("marks") ? q["marks"] : null, 1))
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
}
