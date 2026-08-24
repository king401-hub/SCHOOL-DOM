using System;
using System.Collections.Generic;

namespace SchoolDom.Rfid.Win7
{
    // Persisted app state - serialized as JSON (via JsonUtil, System.Web.Script.Serialization)
    // and encrypted at rest with DPAPI, same approach as SchoolDom.Cbt.Win7's LocalStore.
    public class AppState
    {
        public string DeviceId { get; set; }
        public string CloudUrl { get; set; }
        public string SchoolName { get; set; }

        // Locally cached student/staff card-UID mapping (Section 1d) - refreshed from
        // the SchoolDom API whenever online, consulted on every scan whether online or
        // not, so a network blip never blocks a legitimate scan from being recognized.
        public List<CardAssignmentRecord> CardAssignments { get; set; }

        // Attendance records captured offline or that failed to sync immediately -
        // flushed oldest-first once connectivity returns (Section 3).
        public List<PendingAttendanceRecord> PendingAttendance { get; set; }

        public AppState()
        {
            CardAssignments = new List<CardAssignmentRecord>();
            PendingAttendance = new List<PendingAttendanceRecord>();
        }
    }

    public class CardAssignmentRecord
    {
        public string StudentId { get; set; }
        public string StudentName { get; set; }
        public string CardUid { get; set; }
        public string Status { get; set; } // "active" | "revoked"
    }

    public class PendingAttendanceRecord
    {
        // Client-generated idempotency key (Section 3) - the same value is sent on
        // every retry so a partially-succeeded request never double-records.
        public string IdempotencyKey { get; set; }
        public string CardUid { get; set; }
        public string StudentId { get; set; }
        public string ScannedAtUtc { get; set; }
        public string ReaderType { get; set; }
        public string ReaderName { get; set; }
        public int AttemptCount { get; set; }
        public string LastAttemptError { get; set; }
    }

    // UI-only row for the live scan feed - never persisted, just what MainForm renders.
    internal sealed class ScanFeedEntry
    {
        public DateTime ScannedAtLocal { get; set; }
        public string Uid { get; set; }
        public string StudentName { get; set; }
        public bool Matched { get; set; }
        public ReaderType SourceReaderType { get; set; }
        public string SourceReaderName { get; set; }
    }
}
