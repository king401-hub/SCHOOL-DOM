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
        private readonly SyncService _sync;

        private StatusPill _hidStatusPill;
        private StatusPill _sdkStatusPill;
        private StatusPill _pendingSyncPill;
        private CheckBox _globalCaptureToggle;
        private ListView _feedList;
        private Panel _unregisteredBanner;
        private Panel _unregisteredBannerDot;
        private Label _unregisteredBannerLabel;
        private Label _operatorLabel;
        private readonly Timer _bannerTimer = new Timer { Interval = 4000 };
        // Section 3 "background retry mechanism" - flushes the offline queue every
        // 20s regardless of how it got new entries (a scan, or a stalled retry from
        // last tick), so a connection coming back doesn't need a manual nudge.
        private readonly Timer _syncTimer = new Timer { Interval = 20000 };

        public MainForm()
        {
            _sync = new SyncService(_store);

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
            _syncTimer.Tick += (s, e) => RunFlush();

            Load += OnLoad;
            FormClosing += (s, e) => { _readerManager.Dispose(); _syncTimer.Stop(); };
        }

        private void OnLoad(object sender, EventArgs e)
        {
            if (string.IsNullOrWhiteSpace(_store.State.AccessToken))
            {
                if (!PromptSignIn())
                {
                    Application.Exit();
                    return;
                }
            }

            RefreshOperatorLabel();
            _readerManager.Start();
            _syncTimer.Start();
            RefreshPendingSyncCount();

            try
            {
                _sync.PullCardAssignments();
            }
            catch (CloudAuthExpiredException)
            {
                PromptSignIn();
            }
            catch (Exception ex)
            {
                // Offline on first launch, or the server is unreachable - not fatal,
                // Section 1d's local cache (possibly empty on a first run) still
                // governs matching until the next successful pull.
                ShowBanner("Could not refresh the card list from the cloud: " + ex.Message, Palette.Gold, Palette.GoldSoft);
            }
        }

        private bool PromptSignIn()
        {
            using (var login = new LoginForm(_sync))
            {
                var result = login.ShowDialog(this);
                if (result == DialogResult.OK)
                {
                    RefreshOperatorLabel();
                    return true;
                }
                return false;
            }
        }

        private void RunFlush()
        {
            try
            {
                _sync.FlushPendingQueue();
                RefreshPendingSyncCount();
                // Section 1d: "refreshed from the SchoolDom API whenever online" -
                // piggybacks on the same 20s tick rather than a separate timer.
                _sync.PullCardAssignments();
            }
            catch (CloudAuthExpiredException)
            {
                _syncTimer.Stop();
                PromptSignIn();
                _syncTimer.Start();
            }
            catch (Exception)
            {
                // Network still down - RefreshPendingSyncCount already reflects
                // whatever FlushPendingQueue managed before it stopped; just retry
                // on the next tick rather than surfacing every transient failure.
            }
        }

        private void BuildLayout()
        {
            // Dock order matters and is easy to get backwards: WinForms docks
            // controls in the order added, so DockStyle.Fill must be added FIRST -
            // otherwise Fill claims the entire client area before Left gets a chance
            // to reserve its 240px, and the sidebar just renders on top of it instead
            // of beside it (which is exactly what happened here - see the commit this
            // comment shipped in for the diagnostic dump that caught it).
            Controls.Add(BuildContent());
            Controls.Add(BuildSidebar());
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

            sidebar.Controls.Add(BuildNavButton("Dashboard", 110, active: true, onClick: null));
            sidebar.Controls.Add(BuildNavButton("Assign Cards", 154, active: false, onClick: (s, e) => OpenCardAssignment()));
            sidebar.Controls.Add(BuildNavButton("Bulk Assign", 198, active: false, onClick: (s, e) => OpenBulkAssign()));

            _operatorLabel = new Label
            {
                Text = "",
                Left = 24,
                Top = 660,
                Width = 200,
                Height = 40,
                Font = Palette.Caption,
                ForeColor = Palette.SoftText,
                Anchor = AnchorStyles.Bottom | AnchorStyles.Left
            };
            sidebar.Controls.Add(_operatorLabel);

            var signOut = new LinkLabel
            {
                Text = "Sign Out",
                Left = 24,
                Top = 700,
                AutoSize = true,
                LinkColor = Palette.SoftText,
                ActiveLinkColor = Color.White,
                Font = Palette.Caption,
                Anchor = AnchorStyles.Bottom | AnchorStyles.Left
            };
            signOut.LinkClicked += (s, e) =>
            {
                _sync.SignOut();
                if (!PromptSignIn()) Application.Exit();
            };
            sidebar.Controls.Add(signOut);

            return sidebar;
        }

        private Panel BuildNavButton(string text, int top, bool active, EventHandler onClick)
        {
            var button = new Panel { Left = 0, Top = top, Width = 240, Height = 44, BackColor = active ? Palette.SideButton : Palette.Navy, Cursor = onClick != null ? Cursors.Hand : Cursors.Default };
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
                ForeColor = active ? Color.White : Palette.SoftText,
                Cursor = onClick != null ? Cursors.Hand : Cursors.Default
            };
            button.Controls.Add(accent);
            button.Controls.Add(label);

            if (onClick != null)
            {
                button.Click += onClick;
                label.Click += onClick;
                label.MouseEnter += (s, e) => label.ForeColor = Color.White;
                label.MouseLeave += (s, e) => label.ForeColor = Palette.SoftText;
            }
            return button;
        }

        private void RefreshOperatorLabel()
        {
            var name = string.IsNullOrWhiteSpace(_store.State.OperatorName) ? "Signed in" : _store.State.OperatorName;
            var school = string.IsNullOrWhiteSpace(_store.State.SchoolName) ? "" : "\n" + _store.State.SchoolName;
            _operatorLabel.Text = name + school;
        }

        private void OpenCardAssignment()
        {
            using (var form = new CardAssignmentForm(_readerManager, _sync, _store))
            {
                form.ShowDialog(this);
            }
        }

        private void OpenBulkAssign()
        {
            using (var form = new BulkAssignForm(_readerManager, _sync))
            {
                form.ShowDialog(this);
            }
        }

        private Panel BuildContent()
        {
            // No Padding here - every child below already positions itself with its
            // own Left=32 margin. Panel.Padding would double up on top of that AND
            // feed into AutoScrollMinSize, silently widening the scrollable area.
            var content = new Panel { Dock = DockStyle.Fill, BackColor = Palette.Background, AutoScroll = true };

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
            var banner = new Panel { Left = 32, Top = 104, Width = 880, Height = 44, BackColor = Palette.CoralSoft, Visible = false };
            _unregisteredBannerDot = new Panel { Left = 16, Top = 16, Width = 10, Height = 10, BackColor = Palette.Coral };
            _unregisteredBannerLabel = new Label
            {
                Left = 38,
                Top = 0,
                Height = 44,
                Width = 820,
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
            var card = new Card { Left = 32, Top = 160, Width = 880, Height = 108 };
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
            var card = new Card { Left = 32, Top = 284, Width = 880, Height = 400 };
            card.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Bottom;

            var title = new Label { Text = "Recent Scans", Left = 20, Top = 16, AutoSize = true, Font = Palette.BodyBold, ForeColor = Palette.Text };
            card.Controls.Add(title);

            _feedList = BuildFeedListView();
            _feedList.Left = 20;
            _feedList.Top = 48;
            _feedList.Width = 840;
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
            list.Columns.Add("", 70);
            list.Columns.Add("Card UID", 180);
            list.Columns.Add("Student", 260);
            list.Columns.Add("Reader", 170);
            list.Columns.Add("Time", 140);

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
            if (_readerManager.AssignmentModeActive) return;

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
