using System;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;

namespace SchoolDom.Cbt.Win7
{
    public class LocalStore
    {
        private readonly string _storePath;
        // Entropy scopes encryption to this application so other apps cannot decrypt
        private static readonly byte[] _entropy = Encoding.UTF8.GetBytes("SchoolDom.CBTWin7.LocalStore.v1");
        public AppState State { get; private set; }

        public LocalStore()
        {
            var folder = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "SchoolDom", "CBTWin7");
            Directory.CreateDirectory(folder);
            _storePath = Path.Combine(folder, "store.bin");
            Load();
        }

        public void Load()
        {
            // Migrate from legacy plain-text store.json if it exists
            var legacyPath = Path.Combine(Path.GetDirectoryName(_storePath), "store.json");
            if (!File.Exists(_storePath) && File.Exists(legacyPath))
            {
                var legacyJson = File.ReadAllText(legacyPath);
                State = JsonUtil.Deserialize<AppState>(legacyJson) ?? new AppState();
                EnsureDefaults();
                Save();
                try { File.Delete(legacyPath); } catch { }
                return;
            }

            if (!File.Exists(_storePath))
            {
                State = new AppState();
                Save();
                return;
            }

            try
            {
                var encrypted = File.ReadAllBytes(_storePath);
                var jsonBytes = ProtectedData.Unprotect(encrypted, _entropy, DataProtectionScope.CurrentUser);
                var json = Encoding.UTF8.GetString(jsonBytes);
                State = JsonUtil.Deserialize<AppState>(json) ?? new AppState();
            }
            catch
            {
                // If decryption fails (e.g. different user account), start fresh
                State = new AppState();
            }
            EnsureDefaults();
        }

        public void Save()
        {
            var json = JsonUtil.Serialize(State);
            var jsonBytes = Encoding.UTF8.GetBytes(json);
            var encrypted = ProtectedData.Protect(jsonBytes, _entropy, DataProtectionScope.CurrentUser);
            File.WriteAllBytes(_storePath, encrypted);
        }

        private void EnsureDefaults()
        {
            if (string.IsNullOrWhiteSpace(State.DeviceId)) State.DeviceId = "device_" + Guid.NewGuid().ToString("N");
            if (State.Students == null) State.Students = new System.Collections.Generic.List<StudentRecord>();
            if (State.Exams == null) State.Exams = new System.Collections.Generic.List<ExamRecord>();
            if (State.Sessions == null) State.Sessions = new System.Collections.Generic.List<SessionRecord>();
        }

        public StudentRecord FindStudent(string studentId)
        {
            var value = (studentId ?? "").Trim();
            return State.Students.FirstOrDefault(s => string.Equals(s.StudentId, value, StringComparison.OrdinalIgnoreCase));
        }

        public ExamRecord FindExamByPin(string pin)
        {
            var hash = JsonUtil.Sha256((pin ?? "").Trim());
            return State.Exams.FirstOrDefault(e => string.Equals(e.PinHash, hash, StringComparison.OrdinalIgnoreCase));
        }

        public SessionRecord StartOrResumeSession(ExamRecord exam, StudentRecord student)
        {
            var existing = State.Sessions.FirstOrDefault(s =>
                s.ExamId == exam.Id &&
                string.Equals(s.StudentId, student.StudentId, StringComparison.OrdinalIgnoreCase));

            if (existing != null) return existing;

            var start = DateTime.UtcNow;
            var session = new SessionRecord
            {
                Id = "session_" + Guid.NewGuid().ToString("N"),
                ExamId = exam.Id,
                StudentId = student.StudentId,
                StartedAt = start.ToString("o"),
                EndsAt = start.AddSeconds(Math.Max(60, exam.DurationSeconds)).ToString("o")
            };
            session.AuditLogs.Add(new ActivityLogRecord
            {
                Type = "session_started",
                Message = "Student started an offline CBT session.",
                CreatedAt = JsonUtil.IsoNow()
            });
            State.Sessions.Add(session);
            Save();
            return session;
        }
    }
}

