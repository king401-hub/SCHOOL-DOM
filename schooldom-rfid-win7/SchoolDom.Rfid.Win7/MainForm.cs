using System;
using System.Drawing;
using System.Windows.Forms;
using SchoolDom.Rfid.Win7.Controls;

namespace SchoolDom.Rfid.Win7
{
    public sealed class MainForm : Form
    {
        private readonly LocalStore _store = new LocalStore();
        private readonly ReaderManager _readerManager = new ReaderManager();

        private StatusPill _hidStatusPill;
        private StatusPill _sdkStatusPill;
        private StatusPill _pendingSyncPill;
        private CheckBox _globalCaptureToggle;
        private ListView _feedList;
        private Panel _unregisteredBanner;
        private Panel _unregisteredBannerDot;
        private Label _unregisteredBannerLabel;
        private readonly Timer _bannerTimer = new Timer { Interval = 4000 };

        public MainForm()
        {
            Text = "SchoolDom RFID Attendance";
            Width = 1180;
            Height = 760;
            MinimumSize = new Size(980, 640);
            StartPosition = FormStartPosition.CenterScreen;
            BackColor = Palette.Background;
            Font = Palette.Body;
            Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath);

            BuildLayout();
            WireReaderManager();

            _bannerTimer.Tick += (s, e) => { _bannerTimer.Stop(); _unregisteredBanner.Visible = false; };

            Load += (s, e) => _readerManager.Start();
            FormClosing += (s, e) => _readerManager.Dispose();
        }

        private void BuildLayout()
        {
            Controls.Add(BuildSidebar());
            Controls.Add(BuildContent());
        }

        private Panel BuildSidebar()
        {
            var sidebar = new Panel { Dock = DockStyle.Left, Width = 240, BackColor = Palette.Navy };

            var title = new Label
            {
                Text = "SchoolDom",
                Left = 24,
                Top = 28,
                AutoSize = true,
                Font = Palette.Title,
                ForeColor = Color.White
            };
            var subtitle = new Label
            {
                Text = "RFID Attendance",
                Left = 24,
                Top = 58,
                AutoSize = true,
                Font = Palette.Body,
                ForeColor = Palette.SoftText
            };
            sidebar.Controls.Add(title);
            sidebar.Controls.Add(subtitle);

            var nav = BuildNavButton("Dashboard", 110, active: true);
            sidebar.Controls.Add(nav);

            return sidebar;
        }

        private Panel BuildNavButton(string text, int top, bool active)
        {
            var button = new Panel { Left = 0, Top = top, Width = 240, Height = 44, BackColor = active ? Palette.SideButton : Palette.Navy };
            var accent = new Panel { Left = 0, Top = 0, Width = 4, Height = 44, BackColor = active ? Palette.Blue : Palette.Navy };
            var label = new Label
            {
                Text = text,
                Left = 24,
                Top = 0,
                Height = 44,
                AutoSize = false,
                Width = 200,
                TextAlign = ContentAlignment.MiddleLeft,
                Font = Palette.BodyBold,
                ForeColor = active ? Color.White : Palette.SoftText
            };
            button.Controls.Add(accent);
            button.Controls.Add(label);
            return button;
        }

        private Panel BuildContent()
        {
            var content = new Panel { Dock = DockStyle.Fill, BackColor = Palette.Background, AutoScroll = true, Padding = new Padding(32) };

            var header = new Label
            {
                Text = "Live Attendance Capture",
                Left = 32,
                Top = 28,
                AutoSize = true,
                Font = Palette.Display,
                ForeColor = Palette.Text
            };
            var headerSub = new Label
            {
                Text = "Works with any connected reader — USB HID or SDK/serial — auto-detected.",
                Left = 32,
                Top = 68,
                AutoSize = true,
                Font = Palette.Subtitle,
                ForeColor = Palette.Muted
            };
            content.Controls.Add(header);
            content.Controls.Add(headerSub);

            _unregisteredBanner = BuildUnregisteredBanner();
            content.Controls.Add(_unregisteredBanner);

            content.Controls.Add(BuildReaderStatusCard());
            content.Controls.Add(BuildScanFeedCard());

            return content;
        }

        private Panel BuildUnregisteredBanner()
        {
            var banner = new Panel { Left = 32, Top = 104, Width = 1080, Height = 44, BackColor = Palette.CoralSoft, Visible = false };
            _unregisteredBannerDot = new Panel { Left = 16, Top = 16, Width = 10, Height = 10, BackColor = Palette.Coral };
            _unregisteredBannerLabel = new Label
            {
                Left = 38,
                Top = 0,
                Height = 44,
                Width = 1020,
                TextAlign = ContentAlignment.MiddleLeft,
                Font = Palette.BodyBold,
                ForeColor = Palette.Coral,
                Text = "Unregistered card scanned."
            };
            banner.Controls.Add(_unregisteredBannerDot);
            banner.Controls.Add(_unregisteredBannerLabel);
            banner.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
            return banner;
        }

        private Card BuildReaderStatusCard()
        {
            var card = new Card { Left = 32, Top = 160, Width = 1080, Height = 108 };
            card.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;

            var title = new Label { Text = "Readers", Left = 20, Top = 16, AutoSize = true, Font = Palette.BodyBold, ForeColor = Palette.Text };
            card.Controls.Add(title);

            var hidLabel = new Label { Text = "USB HID (keyboard-emulation)", Left = 20, Top = 44, AutoSize = true, Font = Palette.Body, ForeColor = Palette.Muted };
            _hidStatusPill = new StatusPill { Left = 260, Top = 40 };
            card.Controls.Add(hidLabel);
            card.Controls.Add(_hidStatusPill);

            var sdkLabel = new Label { Text = "SDK / Serial", Left = 20, Top = 74, AutoSize = true, Font = Palette.Body, ForeColor = Palette.Muted };
            _sdkStatusPill = new StatusPill { Left = 260, Top = 70 };
            card.Controls.Add(sdkLabel);
            card.Controls.Add(_sdkStatusPill);

            _globalCaptureToggle = new CheckBox
            {
                Text = "Capture scans system-wide (recommended)",
                Left = 560,
                Top = 42,
                AutoSize = true,
                Checked = true,
                Font = Palette.Body,
                ForeColor = Palette.Text
            };
            _globalCaptureToggle.CheckedChanged += (s, e) =>
                _readerManager.HidReader.GlobalCaptureEnabled = _globalCaptureToggle.Checked;
            card.Controls.Add(_globalCaptureToggle);

            _pendingSyncPill = new StatusPill { Left = 560, Top = 70 };
            _pendingSyncPill.SetState("0 pending sync", Palette.Muted, Palette.LightButton);
            card.Controls.Add(_pendingSyncPill);

            return card;
        }

        private Card BuildScanFeedCard()
        {
            var card = new Card { Left = 32, Top = 284, Width = 1080, Height = 400 };
            card.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Bottom;

            var title = new Label { Text = "Recent Scans", Left = 20, Top = 16, AutoSize = true, Font = Palette.BodyBold, ForeColor = Palette.Text };
            card.Controls.Add(title);

            _feedList = BuildFeedListView();
            _feedList.Left = 20;
            _feedList.Top = 48;
            _feedList.Width = 1040;
            _feedList.Height = 336;
            _feedList.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Bottom;
            card.Controls.Add(_feedList);

            return card;
        }

        private ListView BuildFeedListView()
        {
            var list = new ListView
            {
                View = View.Details,
                OwnerDraw = true,
                FullRowSelect = true,
                GridLines = false,
                HeaderStyle = ColumnHeaderStyle.Nonclickable,
                BorderStyle = BorderStyle.None,
                Font = Palette.Body,
                BackColor = Palette.Surface
            };
            list.Columns.Add("", 90);
            list.Columns.Add("Card UID", 220);
            list.Columns.Add("Student", 320);
            list.Columns.Add("Reader", 200);
            list.Columns.Add("Time", 190);

            list.DrawColumnHeader += (s, e) =>
            {
                using (var brush = new SolidBrush(Palette.LightButton))
                    e.Graphics.FillRectangle(brush, e.Bounds);
                TextRenderer.DrawText(e.Graphics, e.Header.Text, Palette.Caption,
                    e.Bounds, Palette.Muted, TextFormatFlags.Left | TextFormatFlags.VerticalCenter | TextFormatFlags.LeftAndRightPadding);
            };

            list.DrawItem += (s, e) => { };

            list.DrawSubItem += (s, e) =>
            {
                var entry = e.Item.Tag as ScanFeedEntry;
                var rowBack = e.ItemIndex % 2 == 0 ? Palette.Surface : Palette.Background;
                using (var brush = new SolidBrush(rowBack))
                    e.Graphics.FillRectangle(brush, e.Bounds);

                if (entry == null) return;

                switch (e.ColumnIndex)
                {
                    case 0:
                        var dotColor = entry.Matched ? Palette.Green : Palette.Coral;
                        var dotRect = new Rectangle(e.Bounds.Left + 14, e.Bounds.Top + (e.Bounds.Height - 10) / 2, 10, 10);
                        using (var dotBrush = new SolidBrush(dotColor))
                            e.Graphics.FillEllipse(dotBrush, dotRect);
                        break;
                    case 1:
                        TextRenderer.DrawText(e.Graphics, entry.Uid, Palette.Mono, e.Bounds, Palette.Text,
                            TextFormatFlags.Left | TextFormatFlags.VerticalCenter | TextFormatFlags.LeftAndRightPadding);
                        break;
                    case 2:
                        var name = entry.Matched ? entry.StudentName : "Unregistered card";
                        var color = entry.Matched ? Palette.Text : Palette.Coral;
                        TextRenderer.DrawText(e.Graphics, name, Palette.BodyBold, e.Bounds, color,
                            TextFormatFlags.Left | TextFormatFlags.VerticalCenter | TextFormatFlags.LeftAndRightPadding);
                        break;
                    case 3:
                        TextRenderer.DrawText(e.Graphics, entry.SourceReaderName, Palette.Caption, e.Bounds, Palette.Muted,
                            TextFormatFlags.Left | TextFormatFlags.VerticalCenter | TextFormatFlags.LeftAndRightPadding);
                        break;
                    case 4:
                        TextRenderer.DrawText(e.Graphics, entry.ScannedAtLocal.ToString("HH:mm:ss"), Palette.Caption, e.Bounds, Palette.Muted,
                            TextFormatFlags.Left | TextFormatFlags.VerticalCenter | TextFormatFlags.LeftAndRightPadding);
                        break;
                }
            };

            return list;
        }

        private void WireReaderManager()
        {
            _readerManager.CardScanned += OnCardScanned;
            _readerManager.ReaderError += OnReaderError;
            _readerManager.ReadersChanged += (s, e) => RefreshReaderStatus();
            RefreshReaderStatus();
        }

        private void RefreshReaderStatus()
        {
            if (_readerManager.HidReader.IsConnected)
                _hidStatusPill.SetState("Listening", Palette.Green, Palette.GreenSoft);
            else
                _hidStatusPill.SetState("Not installed", Palette.Coral, Palette.CoralSoft);

            var sdkCount = 0;
            foreach (var reader in _readerManager.ActiveReaders)
                if (reader.ReaderType != ReaderType.HidKeyboardEmulation) sdkCount++;

            if (sdkCount > 0)
                _sdkStatusPill.SetState(sdkCount + " connected", Palette.Green, Palette.GreenSoft);
            else
                _sdkStatusPill.SetState("None configured", Palette.Muted, Palette.LightButton);
        }

        // Section 1d - shared scan handling, regardless of which reader produced the scan.
        private void OnCardScanned(object sender, CardScannedEventArgs e)
        {
            var assignment = _store.FindActiveAssignment(e.Uid);
            var entry = new ScanFeedEntry
            {
                ScannedAtLocal = e.ScannedAtUtc.ToLocalTime(),
                Uid = e.Uid,
                Matched = assignment != null,
                StudentName = assignment != null ? assignment.StudentName : null,
                SourceReaderType = e.SourceReaderType,
                SourceReaderName = e.SourceReaderName
            };
            PrependFeedEntry(entry);

            if (assignment != null)
            {
                _store.EnqueuePendingAttendance(new PendingAttendanceRecord
                {
                    IdempotencyKey = Guid.NewGuid().ToString("N"),
                    CardUid = e.Uid,
                    StudentId = assignment.StudentId,
                    ScannedAtUtc = e.ScannedAtUtc.ToString("o"),
                    ReaderType = e.SourceReaderType.ToString(),
                    ReaderName = e.SourceReaderName
                });
                RefreshPendingSyncCount();
            }
            else
            {
                ShowBanner("Unregistered card scanned: " + e.Uid + " — not linked to any student.", Palette.Coral, Palette.CoralSoft);
            }
        }

        private void PrependFeedEntry(ScanFeedEntry entry)
        {
            var item = new ListViewItem(new[] { "", entry.Uid, "", "", "" }) { Tag = entry };
            _feedList.Items.Insert(0, item);
            while (_feedList.Items.Count > 200) _feedList.Items.RemoveAt(_feedList.Items.Count - 1);
        }

        private void RefreshPendingSyncCount()
        {
            var count = _store.State.PendingAttendance.Count;
            if (count == 0)
                _pendingSyncPill.SetState("0 pending sync", Palette.Muted, Palette.LightButton);
            else
                _pendingSyncPill.SetState(count + " pending sync", Palette.Gold, Palette.GoldSoft);
        }

        private void ShowBanner(string message, Color accent, Color tint)
        {
            _unregisteredBannerLabel.Text = message;
            _unregisteredBannerLabel.ForeColor = accent;
            _unregisteredBannerDot.BackColor = accent;
            _unregisteredBanner.BackColor = tint;
            _unregisteredBanner.Visible = true;
            _bannerTimer.Stop();
            _bannerTimer.Start();
        }

        private void OnReaderError(object sender, ReaderErrorEventArgs e)
        {
            if (e.IsFatal)
            {
                MessageBox.Show(this, e.Message, "Reader Error", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            }
            else
            {
                ShowBanner(e.Message, Palette.Gold, Palette.GoldSoft);
            }
        }
    }
}
