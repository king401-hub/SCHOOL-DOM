using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text.RegularExpressions;
using System.Windows.Forms;

namespace SchoolDom.Rfid.Win7
{
    // The one class the rest of the app (Forms, sync layer) talks to. It owns every
    // IRfidReader instance, decides which implementation handles a given physical
    // device, and republishes CardScanned/ReaderError/ReadersChanged as single unified
    // events so a Form never has to know how many readers are plugged in or of what
    // kind. Must be constructed on the UI thread - both the keyboard hook and
    // RegisterDeviceNotification deliver on the thread that owns the message loop.
    internal sealed class ReaderManager : IDisposable
    {
        // Hidden message-only-style window whose sole job is to receive WM_DEVICECHANGE -
        // kept private to ReaderManager so no Form needs to override WndProc itself.
        private sealed class NotificationWindow : NativeWindow
        {
            public event EventHandler<Message> DeviceChanged;

            public NotificationWindow()
            {
                CreateHandle(new CreateParams());
            }

            protected override void WndProc(ref Message m)
            {
                if (m.Msg == NativeInterop.WM_DEVICECHANGE)
                {
                    var handler = DeviceChanged;
                    if (handler != null) handler(this, m);
                }
                base.WndProc(ref m);
            }
        }

        // Registered known vendor/product IDs -> factory for that vendor's SDK reader.
        // Empty until a real reader SDK is supplied (see SdkRfidReader.cs). Keyed by
        // "VID_xxxx&PID_xxxx" (uppercase hex, as it appears in the USB device path).
        private readonly Dictionary<string, Func<IRfidReader>> _sdkFactories =
            new Dictionary<string, Func<IRfidReader>>(StringComparer.OrdinalIgnoreCase);

        private readonly Dictionary<string, IRfidReader> _activeSdkReaders =
            new Dictionary<string, IRfidReader>(StringComparer.OrdinalIgnoreCase);

        private static readonly Regex VidPidPattern =
            new Regex(@"VID_([0-9A-F]{4})&PID_([0-9A-F]{4})", RegexOptions.IgnoreCase | RegexOptions.Compiled);

        private readonly NotificationWindow _window;
        private IntPtr _deviceNotifyHandle = IntPtr.Zero;
        private readonly HidRfidReader _hidReader = new HidRfidReader();
        private bool _started;

        public event EventHandler<CardScannedEventArgs> CardScanned;
        public event EventHandler<ReaderErrorEventArgs> ReaderError;
        public event EventHandler ReadersChanged;

        public HidRfidReader HidReader { get { return _hidReader; } }

        // Section 4b/4c "listening mode" - CardAssignmentForm/BulkAssignForm set this
        // while open so MainForm's normal attendance handling (queueing a
        // PendingAttendanceRecord, showing the "unregistered card" banner) doesn't
        // also fire for a scan that's actually meant to assign a card. Both forms
        // still read scans through the same CardScanned event and the same
        // IRfidReader implementations - this only gates what MainForm does with them.
        public bool AssignmentModeActive { get; set; }

        public IEnumerable<IRfidReader> ActiveReaders
        {
            get
            {
                yield return _hidReader;
                foreach (var reader in _activeSdkReaders.Values)
                    yield return reader;
            }
        }

        public ReaderManager()
        {
            _window = new NotificationWindow();
            _window.DeviceChanged += OnDeviceChanged;

            _hidReader.CardScanned += OnAnyReaderCardScanned;
            _hidReader.ReaderError += OnAnyReaderError;
            _hidReader.ConnectionChanged += (s, e) => RaiseReadersChanged();
        }

        // Call once, after wiring up the UI's event handlers, e.g. from MainForm.Load.
        public void Start()
        {
            if (_started) return;
            _started = true;

            RegisterForDeviceNotifications();
            // HID keyboard-emulation readers can't be reliably distinguished from a real
            // keyboard by VID/PID alone (many are built on generic HID controller
            // chips), so unlike SDK readers there is no per-device match step - the hook
            // simply stays installed and the timing heuristic in HidRfidReader.cs is
            // what actually separates a card scan from typing. Section 1b's settings
            // toggle (HidReader.GlobalCaptureEnabled) is how an admin turns this off.
            _hidReader.Connect();

            RescanForKnownSdkDevices();
        }

        // Extension point used by a new SdkRfidReader implementation (see the comment
        // block at the bottom of SdkRfidReader.cs) - never called from HidRfidReader
        // or from any Form.
        public void RegisterSdkFactory(string vendorId, string productId, Func<IRfidReader> factory)
        {
            _sdkFactories["VID_" + vendorId.ToUpperInvariant() + "&PID_" + productId.ToUpperInvariant()] = factory;
        }

        private void RegisterForDeviceNotifications()
        {
            var filter = new NativeInterop.DEV_BROADCAST_DEVICEINTERFACE
            {
                dbcc_devicetype = NativeInterop.DBT_DEVTYP_DEVICEINTERFACE,
                dbcc_classguid = NativeInterop.GUID_DEVINTERFACE_USB_DEVICE,
                dbcc_name = ""
            };
            filter.dbcc_size = Marshal.SizeOf(filter);

            var buffer = Marshal.AllocHGlobal(filter.dbcc_size);
            try
            {
                Marshal.StructureToPtr(filter, buffer, false);
                _deviceNotifyHandle = NativeInterop.RegisterDeviceNotification(
                    _window.Handle, buffer,
                    NativeInterop.DEVICE_NOTIFY_WINDOW_HANDLE | NativeInterop.DEVICE_NOTIFY_ALL_INTERFACE_CLASSES);

                if (_deviceNotifyHandle == IntPtr.Zero)
                {
                    RaiseError("Could not register for USB device notifications (Win32 error " +
                               Marshal.GetLastWin32Error() + "). Newly plugged-in SDK readers will only be " +
                               "picked up after restarting the app.", isFatal: false);
                }
            }
            finally
            {
                // RegisterDeviceNotification copies the filter internally - safe to free now.
                Marshal.FreeHGlobal(buffer);
            }
        }

        private void OnDeviceChanged(object sender, Message m)
        {
            var eventType = m.WParam.ToInt32();
            if (eventType != NativeInterop.DBT_DEVICEARRIVAL && eventType != NativeInterop.DBT_DEVICEREMOVECOMPLETE)
                return;

            // WM_DEVICECHANGE fires for every device class, not just the USB interface
            // we filtered for - re-enumerate rather than trust lParam alone, so a
            // spurious/unparsable notification never leaves state stale.
            RescanForKnownSdkDevices();
        }

        // Compares currently-plugged VID/PID device paths against the registered SDK
        // factories, connecting newly-arrived matches and disconnecting/disposing ones
        // that were unplugged. A no-op (both dictionaries stay empty) until a real
        // vendor SDK is registered via RegisterSdkFactory.
        private void RescanForKnownSdkDevices()
        {
            if (_sdkFactories.Count == 0) return;

            var present = EnumeratePresentVidPidKeys();

            foreach (var key in new List<string>(_activeSdkReaders.Keys))
            {
                if (!present.Contains(key))
                {
                    var reader = _activeSdkReaders[key];
                    _activeSdkReaders.Remove(key);
                    reader.CardScanned -= OnAnyReaderCardScanned;
                    reader.ReaderError -= OnAnyReaderError;
                    reader.Dispose();
                    RaiseReadersChanged();
                }
            }

            foreach (var key in present)
            {
                Func<IRfidReader> factory;
                if (!_sdkFactories.TryGetValue(key, out factory)) continue;
                if (_activeSdkReaders.ContainsKey(key)) continue;

                var reader = factory();
                reader.CardScanned += OnAnyReaderCardScanned;
                reader.ReaderError += OnAnyReaderError;
                reader.Connect();
                _activeSdkReaders[key] = reader;
                RaiseReadersChanged();
            }
        }

        private static HashSet<string> EnumeratePresentVidPidKeys()
        {
            var result = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            try
            {
                using (var searcher = new System.Management.ManagementObjectSearcher(
                    "SELECT DeviceID FROM Win32_PnPEntity WHERE DeviceID LIKE 'USB%'"))
                {
                    foreach (System.Management.ManagementObject device in searcher.Get())
                    {
                        var deviceId = device["DeviceID"] as string;
                        if (string.IsNullOrEmpty(deviceId)) continue;
                        var match = VidPidPattern.Match(deviceId);
                        if (match.Success)
                            result.Add("VID_" + match.Groups[1].Value.ToUpperInvariant() + "&PID_" + match.Groups[2].Value.ToUpperInvariant());
                    }
                }
            }
            catch
            {
                // WMI unavailable/locked down on this machine - known-SDK devices simply
                // won't be auto-detected until the next successful scan; HID capture is
                // unaffected since it doesn't depend on this enumeration.
            }
            return result;
        }

        private void OnAnyReaderCardScanned(object sender, CardScannedEventArgs e)
        {
            var handler = CardScanned;
            if (handler != null) handler(this, e);
        }

        private void OnAnyReaderError(object sender, ReaderErrorEventArgs e)
        {
            RaiseError(e.Message, e.IsFatal);
        }

        private void RaiseError(string message, bool isFatal)
        {
            var handler = ReaderError;
            if (handler != null) handler(this, new ReaderErrorEventArgs(message, isFatal));
        }

        private void RaiseReadersChanged()
        {
            var handler = ReadersChanged;
            if (handler != null) handler(this, EventArgs.Empty);
        }

        public void Dispose()
        {
            if (_deviceNotifyHandle != IntPtr.Zero)
            {
                NativeInterop.UnregisterDeviceNotification(_deviceNotifyHandle);
                _deviceNotifyHandle = IntPtr.Zero;
            }
            _window.DeviceChanged -= OnDeviceChanged;
            _window.DestroyHandle();

            _hidReader.Dispose();
            foreach (var reader in _activeSdkReaders.Values)
                reader.Dispose();
            _activeSdkReaders.Clear();
        }
    }
}
