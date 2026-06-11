using System;
using System.Collections.Generic;

namespace SchoolDom.Cbt.Win7
{
    public class AppState
    {
        public string DeviceId { get; set; }
        public string ActivePackageId { get; set; }
        public string PackageLockedAt { get; set; }
        public string PackageGeneratedAt { get; set; }
        public string CloudUrl { get; set; }
        public string AccessToken { get; set; }
        public string LastSyncAt { get; set; }
        public string SchoolName { get; set; }
        public string SchoolCode { get; set; }
        public List<StudentRecord> Students { get; set; }
        public List<ExamRecord> Exams { get; set; }
        public List<SessionRecord> Sessions { get; set; }

        public AppState()
        {
            DeviceId = "device_" + Guid.NewGuid().ToString("N");
            CloudUrl = "https://schooldom.academy";
            Students = new List<StudentRecord>();
            Exams = new List<ExamRecord>();
            Sessions = new List<SessionRecord>();
        }
    }

    public class StudentRecord
    {
        public string Id { get; set; }
        public string StudentId { get; set; }
        public string FullName { get; set; }
        public string ClassName { get; set; }
        public string ProfilePicture { get; set; }
        public string ProfilePictureData { get; set; }
    }

    public class ExamRecord
    {
        public string Id { get; set; }
        public string Title { get; set; }
        public string Subject { get; set; }
        public string ClassName { get; set; }
        public int DurationSeconds { get; set; }
        public string StartsAt { get; set; }
        public string EndsAt { get; set; }
        public string Instructions { get; set; }
        public string PinHash { get; set; }
        public List<QuestionRecord> Questions { get; set; }

        public ExamRecord()
        {
            Questions = new List<QuestionRecord>();
        }
    }

    public class QuestionRecord
    {
        public string Id { get; set; }
        public string Text { get; set; }
        public string Type { get; set; }
        public double Points { get; set; }
        public string CorrectAnswer { get; set; }
        public List<string> Options { get; set; }
        public QuestionGroupRecord Group { get; set; }

        public QuestionRecord()
        {
            Options = new List<string>();
        }
    }

    public class QuestionGroupRecord
    {
        public string Title { get; set; }
        public string PassageText { get; set; }
    }

    public class SessionRecord
    {
        public string Id { get; set; }
        public string ExamId { get; set; }
        public string StudentId { get; set; }
        public string StudentName { get; set; }
        public string Status { get; set; }
        public string StartedAt { get; set; }
        public string EndsAt { get; set; }
        public string SubmittedAt { get; set; }
        public string SyncStatus { get; set; }
        public int FocusLossCount { get; set; }
        public Dictionary<string, object> Answers { get; set; }
        public List<ActivityLogRecord> AuditLogs { get; set; }

        public SessionRecord()
        {
            Status = "in_progress";
            SyncStatus = "pending";
            Answers = new Dictionary<string, object>();
            AuditLogs = new List<ActivityLogRecord>();
        }
    }

    public class ActivityLogRecord
    {
        public string Type { get; set; }
        public string Message { get; set; }
        public string CreatedAt { get; set; }
    }
}
