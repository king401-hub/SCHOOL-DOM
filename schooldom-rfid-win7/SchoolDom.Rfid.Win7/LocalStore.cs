using System;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;

namespace SchoolDom.Rfid.Win7
{
    // Same pattern as SchoolDom.Cbt.Win7's LocalStore: JSON state encrypted at rest with
    // DPAPI (CurrentUser scope), so the card-UID/student mapping cache and the pending
    // attendance queue aren't sitting on disk as plain text on a shared school PC.
    public class LocalStore
    {
        private readonly string _storePath;
        private static readonly byte[] _entropy = Encoding.UTF8.GetBytes("SchoolDom.RfidWin7.LocalStore.v1");
        public AppState State { get; private set; }

        public LocalStore()
        {
            var folder = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "SchoolDom", "RfidWin7");
            Directory.CreateDirectory(folder);
            _storePath = Path.Combine(folder, "store.bin");
            Load();
        }

        public void Load()
        {
            if (!File.Exists(_storePath))
            {
                State = new AppState();
                EnsureDefaults();
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
                // Decryption fails under a different Windows user account, or the file
                // is corrupt - start fresh rather than crash the app on launch.
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
            if (string.IsNullOrWhiteSpace(State.DeviceId)) State.DeviceId = "rfid_device_" + Guid.NewGuid().ToString("N");
            if (string.IsNullOrWhiteSpace(State.CloudUrl)) State.CloudUrl = "https://schooldom.academy";
            if (State.CardAssignments == null) State.CardAssignments = new System.Collections.Generic.List<CardAssignmentRecord>();
            if (State.PendingAttendance == null) State.PendingAttendance = new System.Collections.Generic.List<PendingAttendanceRecord>();
        }

        // Section 1d: look up a scanned UID against the locally cached mapping table.
        // Consulted on every scan regardless of connectivity - only "active" assignments
        // count, so a revoked-then-reassigned card can never resolve to its old holder.
        public CardAssignmentRecord FindActiveAssignment(string cardUid)
        {
            var value = (cardUid ?? "").Trim();
            return State.CardAssignments.FirstOrDefault(a =>
                string.Equals(a.CardUid, value, StringComparison.OrdinalIgnoreCase) &&
                string.Equals(a.Status, "active", StringComparison.OrdinalIgnoreCase));
        }

        public void EnqueuePendingAttendance(PendingAttendanceRecord record)
        {
            State.PendingAttendance.Add(record);
            Save();
        }
    }
}
