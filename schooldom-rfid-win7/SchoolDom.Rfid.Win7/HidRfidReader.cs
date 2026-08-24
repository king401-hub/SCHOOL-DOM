using System;
using System.Diagnostics;
using System.Text;
using System.Windows.Forms;

namespace SchoolDom.Rfid.Win7
{
    // Captures scans from plug-and-play USB HID keyboard-emulation readers - the most
    // common/cheapest RFID reader type. These readers show up to Windows as an ordinary
    // USB keyboard and "type" the card UID followed by Enter (occasionally Tab), so
    // there is no vendor SDK to call into: the only way to read them system-wide,
    // independent of which window/field has focus, is a low-level global keyboard hook.
    //
    // Distinguishing a card scan from a human typing in some other field is done purely
    // by inter-keystroke timing: a HID reader "types" its whole payload in a few
    // milliseconds, far faster than any human can type. Keys arriving less than
    // FastKeystrokeThresholdMs apart are buffered as a candidate scan; Enter/Tab commits
    // the buffer; a gap larger than IdleResetMs at any point invalidates the buffer as
    // "not a scan" and it is dropped (never forwarded, so normal typing is unaffected).
    internal sealed class HidRfidReader : IRfidReader, IDisposable
    {
        private const int FastKeystrokeThresholdMs = 50;
        private const int IdleResetMs = 400;

        private readonly StringBuilder _buffer = new StringBuilder();
        // Must hold a reference to the delegate for the hook's lifetime - if it's only
        // passed inline, the GC can collect it while the unmanaged hook still points at
        // it, and the next keystroke crashes the process.
        private readonly NativeInterop.LowLevelKeyboardProc _hookProc;
        private IntPtr _hookHandle = IntPtr.Zero;
        private readonly Stopwatch _stopwatch = Stopwatch.StartNew();
        private long _lastKeyAtMs = -1;
        private bool _bufferLooksLikeScan = true;
        private bool _enabled = true;

        public ReaderType ReaderType { get { return ReaderType.HidKeyboardEmulation; } }
        public string DisplayName { get { return "USB HID Reader (keyboard-emulation)"; } }
        public bool IsConnected { get { return _hookHandle != IntPtr.Zero; } }

        // Settings toggle (Section 1b) - some deployments want focused-field-only
        // capture instead of a system-wide hook. When disabled, the hook is left
        // installed (so re-enabling is instant) but every keystroke is ignored.
        public bool GlobalCaptureEnabled
        {
            get { return _enabled; }
            set { _enabled = value; _buffer.Clear(); }
        }

        public event EventHandler<CardScannedEventArgs> CardScanned;
        public event EventHandler<ReaderErrorEventArgs> ReaderError;
        public event EventHandler ConnectionChanged;

        public HidRfidReader()
        {
            _hookProc = HookCallback;
        }

        public void Connect()
        {
            if (IsConnected) return;

            using (var curProcess = Process.GetCurrentProcess())
            using (var curModule = curProcess.MainModule)
            {
                _hookHandle = NativeInterop.SetWindowsHookEx(
                    NativeInterop.WH_KEYBOARD_LL,
                    _hookProc,
                    NativeInterop.GetModuleHandle(curModule.ModuleName),
                    0);
            }

            if (_hookHandle == IntPtr.Zero)
            {
                RaiseError("Could not install the system-wide keyboard hook (Win32 error " +
                           System.Runtime.InteropServices.Marshal.GetLastWin32Error() +
                           "). USB HID card readers will not be detected until this app is restarted, " +
                           "possibly as Administrator.", isFatal: true);
                return;
            }

            RaiseConnectionChanged();
        }

        public void Disconnect()
        {
            if (!IsConnected) return;
            NativeInterop.UnhookWindowsHookEx(_hookHandle);
            _hookHandle = IntPtr.Zero;
            _buffer.Clear();
            RaiseConnectionChanged();
        }

        private IntPtr HookCallback(int nCode, IntPtr wParam, IntPtr lParam)
        {
            if (nCode >= 0 && _enabled &&
                (wParam == (IntPtr)NativeInterop.WM_KEYDOWN || wParam == (IntPtr)NativeInterop.WM_SYSKEYDOWN))
            {
                var data = (NativeInterop.KBDLLHOOKSTRUCT)System.Runtime.InteropServices.Marshal.PtrToStructure(
                    lParam, typeof(NativeInterop.KBDLLHOOKSTRUCT));
                HandleKeyDown((int)data.vkCode);
            }

            // Always forward to the next hook / the OS - a low-level hook that eats
            // keystrokes breaks every other application on the machine, including this
            // one's own text fields.
            return NativeInterop.CallNextHookEx(_hookHandle, nCode, wParam, lParam);
        }

        private void HandleKeyDown(int vkCode)
        {
            var now = _stopwatch.ElapsedMilliseconds;
            var gap = _lastKeyAtMs < 0 ? long.MaxValue : now - _lastKeyAtMs;
            _lastKeyAtMs = now;

            if (gap > IdleResetMs)
            {
                _buffer.Clear();
                _bufferLooksLikeScan = true;
            }
            else if (_buffer.Length > 0 && gap > FastKeystrokeThresholdMs)
            {
                // Too slow to be a reader mid-payload - a human is typing. Keep tracking
                // the buffer (so a later fast burst still resets cleanly via IdleResetMs)
                // but mark it as disqualified so it's never forwarded as a scan.
                _bufferLooksLikeScan = false;
            }

            if (vkCode == (int)Keys.Return || vkCode == (int)Keys.Tab)
            {
                CommitBuffer();
                return;
            }

            var ch = VirtualKeyToChar(vkCode);
            if (ch.HasValue)
            {
                _buffer.Append(ch.Value);
            }
            else
            {
                // Any key that isn't a plausible UID character (arrows, function keys,
                // modifiers while held alone, etc.) can't be part of a reader payload.
                _bufferLooksLikeScan = false;
            }
        }

        private void CommitBuffer()
        {
            var candidate = _buffer.ToString();
            _buffer.Clear();
            var wasQualified = _bufferLooksLikeScan;
            _bufferLooksLikeScan = true;

            if (!wasQualified || candidate.Length == 0) return;

            var handler = CardScanned;
            if (handler != null)
                handler(this, new CardScannedEventArgs(candidate, ReaderType.HidKeyboardEmulation, DisplayName));
        }

        // Deliberately simple: readers only ever "type" digits and occasionally
        // uppercase letters (hex UIDs), so a full keyboard-layout/shift-state
        // translation (ToUnicode + keyboard state array) would be complexity with no
        // payload it would ever need to decode.
        private static char? VirtualKeyToChar(int vkCode)
        {
            if (vkCode >= 0x30 && vkCode <= 0x39) return (char)('0' + (vkCode - 0x30)); // 0-9
            if (vkCode >= 0x41 && vkCode <= 0x5A) return (char)('A' + (vkCode - 0x41)); // A-Z
            if (vkCode >= 0x60 && vkCode <= 0x69) return (char)('0' + (vkCode - 0x60)); // numpad 0-9
            return null;
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
}
