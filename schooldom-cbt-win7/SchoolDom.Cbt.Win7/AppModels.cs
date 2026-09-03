using System;
using System.Collections.Generic;
using System.Configuration;

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
        // True when submitted results have not yet been uploaded to the cloud
        public bool HasPendingUpload { get; set; }
        public string LastUploadAttemptAt { get; set; }
        // Shared token for UDP LAN discovery — student app must include this to get a response
        public string DiscoveryToken { get; set; }

        // CBT license state, as last reported by the cloud (offline-sync pull or the
        // license-activate endpoint) - never computed locally. LicenseLastVerifiedTickCount
        // is Environment.TickCount captured at the moment that report arrived, which is what
        // LanServerService.HasValidLicenseGrace() anchors its 7-day offline grace window to -
        // a monotonic counter unaffected by the system clock, unlike LicenseLastVerifiedAtUtc
        // (kept only for display).
        public string LicenseStatus { get; set; }
        public string LicenseExpiresAt { get; set; }
        public bool LicenseIsActive { get; set; }
        public string LicenseLastVerifiedAtUtc { get; set; }
        public int LicenseLastVerifiedTickCount { get; set; }

        // "ethernet" (default) or "wifi" - which adapter type the CBT server binds to.
        // Ethernet is preferred automatically; Wi-Fi is only ever used once the admin
        // explicitly switches to it from the dashboard (e.g. a room with no wired LAN
        // run to it), and that choice is remembered across restarts.
        public string PreferredNetworkInterface { get; set; }

        // Set right before the auto-updater launches a silent installer, cleared once a
        // launch shows the app is actually running a newer build. If a later launch finds
        // BOTH still equal to that same (still-outdated) currentVersion/latestVersion pair,
        // the previous silent install evidently didn't take effect (a common failure mode:
        // /VERYSILENT swallows the error if antivirus/Windows hadn't released the file lock
        // on the running exe yet) - see Program.cs.
        public string LastUpdateAttemptFromVersion { get; set; }
        public string LastUpdateAttemptToVersion { get; set; }

        public AppState()
        {
            DeviceId = "device_" + Guid.NewGuid().ToString("N");
            CloudUrl = ConfigurationManager.AppSettings["CloudUrl"] ?? "https://schooldom.academy";
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
        public bool IsActive { get; set; } = true;

        // Full profile fields, synced from the cloud's offline-sync package
        // (backend/exams/exam_views.py _offline_student_payload) - shown on the
        // student terminal's profile view. All optional/blank when the cloud
        // hasn't recorded them, same as everywhere else this data is displayed.
        public string AdmissionNumber { get; set; }
        public string Email { get; set; }
        public string Phone { get; set; }
        public string DateOfBirth { get; set; }
        public string Gender { get; set; }
        public string AdmissionDate { get; set; }
        public string StateOfOrigin { get; set; }
        public string LocalGovernment { get; set; }
        public string GuardianName { get; set; }
        public string GuardianPhone { get; set; }
        public string GuardianEmail { get; set; }
        public string GuardianRelation { get; set; }
        public string SecondGuardianName { get; set; }
        public string SecondGuardianPhone { get; set; }
        public string BloodGroup { get; set; }
        public string Disability { get; set; }
        public string HomeAddress { get; set; }
        public string Allergies { get; set; }
        public string MedicalConditions { get; set; }
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
        public string Image { get; set; }
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
        public string Image { get; set; }
    }

    public class SessionRecord
    {
        public string Id { get; set; }
        public string ExamId { get; set; }
        public string StudentId { get; set; }
        public string StudentName { get; set; }
        public string Status { get; set; }
        public string StartedAt { get; set; }
        public string ExamBeganAt { get; set; }
        public string EndsAt { get; set; }
        public string SubmittedAt { get; set; }
        public string SyncStatus { get; set; }
        public int FocusLossCount { get; set; }
        public Dictionary<string, object> Answers { get; set; }
        public List<ActivityLogRecord> AuditLogs { get; set; }
        // Admin-awarded marks for written/essay questions, keyed by question Id (these cannot be auto-graded)
        public Dictionary<string, double> ManualScores { get; set; }

        public SessionRecord()
        {
            Status = "in_progress";
            SyncStatus = "pending";
            Answers = new Dictionary<string, object>();
            AuditLogs = new List<ActivityLogRecord>();
            ManualScores = new Dictionary<string, double>();
        }
    }

    public class ActivityLogRecord
    {
        public string Type { get; set; }
        public string Message { get; set; }
        public string CreatedAt { get; set; }
    }
}
