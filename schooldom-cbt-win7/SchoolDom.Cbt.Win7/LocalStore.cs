using System;
using System.IO;
using System.Linq;

namespace SchoolDom.Cbt.Win7
{
    public class LocalStore
    {
        private readonly string _storePath;
        public AppState State { get; private set; }

        public LocalStore()
        {
            var folder = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "SchoolDom", "CBTWin7");
            Directory.CreateDirectory(folder);
            _storePath = Path.Combine(folder, "store.json");
            Load();
        }

        public void Load()
        {
            if (!File.Exists(_storePath))
            {
                State = new AppState();
                Save();
                return;
            }

            var json = File.ReadAllText(_storePath);
            State = JsonUtil.Deserialize<AppState>(json) ?? new AppState();
            if (string.IsNullOrWhiteSpace(State.DeviceId)) State.DeviceId = "device_" + Guid.NewGuid().ToString("N");
            if (State.Students == null) State.Students = new System.Collections.Generic.List<StudentRecord>();
            if (State.Exams == null) State.Exams = new System.Collections.Generic.List<ExamRecord>();
            if (State.Sessions == null) State.Sessions = new System.Collections.Generic.List<SessionRecord>();
        }

        public void Save()
        {
            File.WriteAllText(_storePath, JsonUtil.Serialize(State));
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

