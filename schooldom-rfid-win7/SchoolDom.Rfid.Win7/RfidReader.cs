using System;

namespace SchoolDom.Rfid.Win7
{
    // What kind of physical reader produced a scan - logged with every scan so a
    // multi-reader deployment (e.g. one HID reader at the gate, one SDK reader at the
    // office desk) can be debugged from the attendance log alone.
    internal enum ReaderType
    {
        HidKeyboardEmulation,
        SdkVendor,
        SerialGeneric
    }

    internal sealed class CardScannedEventArgs : EventArgs
    {
        public string Uid { get; private set; }
        public ReaderType SourceReaderType { get; private set; }
        public string SourceReaderName { get; private set; }
        public DateTime ScannedAtUtc { get; private set; }

        public CardScannedEventArgs(string uid, ReaderType sourceReaderType, string sourceReaderName)
        {
            Uid = uid;
            SourceReaderType = sourceReaderType;
            SourceReaderName = sourceReaderName;
            ScannedAtUtc = DateTime.UtcNow;
        }
    }

    internal sealed class ReaderErrorEventArgs : EventArgs
    {
        public string Message { get; private set; }
        public bool IsFatal { get; private set; }

        public ReaderErrorEventArgs(string message, bool isFatal)
        {
            Message = message;
            IsFatal = isFatal;
        }
    }

    // Common interface every reader implementation speaks - ReaderManager and the UI
    // only ever program against this, never against a concrete HidRfidReader /
    // SdkRfidReader. To add a new vendor SDK later: implement this interface in a new
    // class (see SdkRfidReader.cs for the extension point), then register it with
    // ReaderManager.RegisterSdkFactory - no changes needed here, in ReaderManager, or
    // in any Form.
    internal interface IRfidReader : IDisposable
    {
        ReaderType ReaderType { get; }
        string DisplayName { get; }
        bool IsConnected { get; }

        event EventHandler<CardScannedEventArgs> CardScanned;
        event EventHandler<ReaderErrorEventArgs> ReaderError;
        event EventHandler ConnectionChanged;

        void Connect();
        void Disconnect();
    }
}
