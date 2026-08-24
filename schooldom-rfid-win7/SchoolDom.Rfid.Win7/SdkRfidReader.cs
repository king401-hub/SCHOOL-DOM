using System;
using System.IO.Ports;
using System.Linq;
using System.Text;

namespace SchoolDom.Rfid.Win7
{
    // Generic serial/COM-port RFID reader - covers the many readers that show up as a
    // virtual COM port (genuine RS-232, or USB-to-serial via a CDC/FTDI/CH340 driver)
    // and just write the UID as ASCII terminated by CR and/or LF. No vendor SDK needed
    // for this class of reader, just System.IO.Ports (built into the BCL).
    //
    // This is registered with ReaderManager the same way a real vendor SDK reader would
    // be (see the extension point at the bottom of this file) - the rest of the app
    // never knows or cares that this one happens to use SerialPort instead of a DLL.
    internal sealed class SerialRfidReader : IRfidReader
    {
        private readonly string _portName;
        private readonly int _baudRate;
        private SerialPort _port;
        private readonly StringBuilder _buffer = new StringBuilder();

        public ReaderType ReaderType { get { return ReaderType.SerialGeneric; } }
        public string DisplayName { get { return "Serial Reader (" + _portName + ")"; } }
        public bool IsConnected { get { return _port != null && _port.IsOpen; } }

        public event EventHandler<CardScannedEventArgs> CardScanned;
        public event EventHandler<ReaderErrorEventArgs> ReaderError;
        public event EventHandler ConnectionChanged;

        public SerialRfidReader(string portName, int baudRate = 9600)
        {
            _portName = portName;
            _baudRate = baudRate;
        }

        public static string[] AvailablePorts()
        {
            return SerialPort.GetPortNames().OrderBy(p => p).ToArray();
        }

        public void Connect()
        {
            if (IsConnected) return;
            try
            {
                _port = new SerialPort(_portName, _baudRate, Parity.None, 8, StopBits.One)
                {
                    NewLine = "\r",
                    ReadTimeout = 500,
                    WriteTimeout = 500
                };
                _port.DataReceived += OnDataReceived;
                _port.Open();
                RaiseConnectionChanged();
            }
            catch (Exception ex)
            {
                // A wrong/missing driver, the port already claimed by another app, or a
                // reader that's simply unplugged all surface here as UnauthorizedAccessException /
                // IOException / ArgumentException - give the admin one clear message instead
                // of a raw .NET exception dialog.
                RaiseError("Could not open " + _portName + " (" + ex.GetType().Name + "): " + ex.Message +
                           ". Check that the reader is plugged in, its driver is installed, and no other " +
                           "program (e.g. another instance of this app) already has the port open.", isFatal: true);
                _port = null;
            }
        }

        public void Disconnect()
        {
            if (_port == null) return;
            try
            {
                _port.DataReceived -= OnDataReceived;
                if (_port.IsOpen) _port.Close();
            }
            catch { /* best-effort close */ }
            finally
            {
                _port.Dispose();
                _port = null;
                _buffer.Clear();
                RaiseConnectionChanged();
            }
        }

        private void OnDataReceived(object sender, SerialDataReceivedEventArgs e)
        {
            try
            {
                var chunk = _port.ReadExisting();
                foreach (var ch in chunk)
                {
                    if (ch == '\r' || ch == '\n')
                    {
                        CommitBuffer();
                    }
                    else
                    {
                        _buffer.Append(ch);
                    }
                }
            }
            catch (Exception ex)
            {
                RaiseError("Lost communication with " + _portName + ": " + ex.Message, isFatal: false);
            }
        }

        private void CommitBuffer()
        {
            var candidate = _buffer.ToString().Trim();
            _buffer.Clear();
            if (candidate.Length == 0) return;

            var handler = CardScanned;
            if (handler != null)
                handler(this, new CardScannedEventArgs(candidate, ReaderType.SerialGeneric, DisplayName));
        }

        private void RaiseConnectionChanged()
        {
            var handler = ConnectionChanged;
            if (handler != null) handler(this, EventArgs.Empty);
        }

        private void RaiseError(string message, bool isFatal)
        {
            var handler = ReaderError;
            if (handler != null) handler(this, new ReaderErrorEventArgs(message, isFatal));
        }

        public void Dispose()
        {
            Disconnect();
        }
    }

    // ============================================================================
    // EXTENSION POINT - adding a new vendor SDK reader
    // ============================================================================
    // No vendor SDK/DLL has been supplied for this project yet, so nothing below is
    // wired in or shipped - this is deliberately left as a template, not a fabricated
    // implementation, per the instruction not to assume/invent a specific reader's
    // binding. When a real reader's SDK is supplied:
    //
    //   1. Add a new class implementing IRfidReader, e.g. AcmeSdkRfidReader, in its own
    //      file (AcmeSdkRfidReader.cs). It will typically:
    //        - [DllImport("acme_rfid.dll")] the vendor's Open/Close/Poll/Read functions
    //        - Either poll on a background Thread/Timer, or marshal a native callback
    //          into a C# delegate the same way HidRfidReader's LowLevelKeyboardProc does
    //        - Raise CardScanned with ReaderType.SdkVendor when a UID is read
    //        - Translate SDK-specific error codes into a clear ReaderError message
    //          (missing DLL -> DllNotFoundException, wrong firmware -> a vendor error
    //          code, driver not installed -> the SDK's own init failure code) instead of
    //          letting a raw native exception surface to the UI
    //   2. Register its known USB vendor/product ID with
    //      ReaderManager.RegisterSdkFactory(vendorId, productId, () => new AcmeSdkRfidReader())
    //      in ReaderManager's constructor.
    //
    // Nothing else changes - ReaderManager and every Form only ever see IRfidReader, so
    // adding a new vendor never touches shared/UI code, matching the constraint that
    // reader-specific behavior must live inside its own implementation.
    // ============================================================================
}
