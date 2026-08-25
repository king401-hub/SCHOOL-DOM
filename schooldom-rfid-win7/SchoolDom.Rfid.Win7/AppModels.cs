using System;
using System.Collections.Generic;

namespace SchoolDom.Rfid.Win7
{
    // Persisted app state - serialized as JSON (via JsonUtil, System.Web.Script.Serialization)
    // and encrypted at rest with DPAPI, same approach as SchoolDom.Cbt.Win7's LocalStore.
    // Every read/write of an AppState instance must hold LocalStore.StateLock - see the
    // comment on that field for why.
    public class AppState
    {
        public string DeviceId { get; set; }
        public string CloudUrl { get; set; }
        public string SchoolName { get; set; }
        public string SchoolCode { get; set; }
        public string AccessToken { get; set; }
        public string OperatorName { get; set; }
        public string LastSyncAtUtc { get; set; }
        public string LastAssignmentsPullAtUtc { get; set; }

        // Locally cached card-UID -> person mapping (Section 1d) - refreshed from the
        // SchoolDom API whenever online, consulted on every scan whether online or
        // not, so a network blip never blocks a legitimate scan from being recognized.
        // Covers students, teachers, and admins - anyone can hold a card.
        public List<CardAssignmentRecord> CardAssignments { get; set; }

        // Attendance records captured offline or that failed to sync immediately -
        // flushed oldest-first once connectivity returns (Section 3).
        public List<PendingAttendanceRecord> PendingAttendance { get; set; }

        // Per-card-UID cooldown: last time this exact card produced an accepted scan,
        // so a card held too close to the reader for too long (which makes some HID
        // readers repeat-fire the same UID) doesn't clock the same person in and back
        // out again a second later. Keyed by UID, value is ISO-8601 UTC.
        public Dictionary<string, string> LastScanAtUtcByCardUid { get; set; }

        public AppState()
        {
            CardAssignments = new List<CardAssignmentRecord>();
            PendingAttendance = new List<PendingAttendanceRecord>();
            LastScanAtUtcByCardUid = new Dictionary<string, string>();
        }
    }

    public class CardAssignmentRecord
    {
        public string PersonId { get; set; }
        public string PersonName { get; set; }
        public string Role { get; set; }
        public string CardUid { get; set; }
        public string Status { get; set; } // "active" | "revoked"
    }

    public class PendingAttendanceRecord
    {
        // Client-generated idempotency key (Section 3) - the same value is sent on
        // every retry so a partially-succeeded request never double-records.
        public string IdempotencyKey { get; set; }
        public string CardUid { get; set; }
        public string PersonId { get; set; }
        public string ScannedAtUtc { get; set; }
        public string ReaderType { get; set; }
        public string ReaderName { get; set; }
        public int AttemptCount { get; set; }
        public string LastAttemptError { get; set; }
    }

    // UI-only lookup rows (Section 4b/4c pickers) - never persisted.
    internal sealed class ClassOption
    {
        public string Id { get; set; }
        public string Label { get; set; }
        public override string ToString() { return Label; }
    }

    internal sealed class PersonOption
    {
        public string Id { get; set; }
        public string Name { get; set; }
        public string Role { get; set; }
        public string RoleLabel { get; set; }
        public string StudentCode { get; set; }
        public string ClassName { get; set; }
        public bool HasActiveCard { get; set; }
        public override string ToString()
        {
            var suffix = !string.IsNullOrEmpty(StudentCode) ? " (" + StudentCode + ")"
                : !string.IsNullOrEmpty(RoleLabel) ? " (" + RoleLabel + ")"
                : "";
            return Name + suffix;
        }
    }

    // UI-only row for the live scan feed - never persisted, just what MainForm renders.
    internal sealed class ScanFeedEntry
    {
        public DateTime ScannedAtLocal { get; set; }
        public string Uid { get; set; }
        public string PersonName { get; set; }
        public bool Matched { get; set; }
        public bool WasCooldown { get; set; }
        public ReaderType SourceReaderType { get; set; }
        public string SourceReaderName { get; set; }
    }

    // Attendance History screen row (pulled fresh from the server, never cached locally).
    internal sealed class AttendanceHistoryEntry
    {
        public string PersonName { get; set; }
        public string Role { get; set; }
        public DateTime? ClockInAt { get; set; }
        public DateTime? ClockOutAt { get; set; }
        public string Status { get; set; }
        public string CardUid { get; set; }
    }
}
