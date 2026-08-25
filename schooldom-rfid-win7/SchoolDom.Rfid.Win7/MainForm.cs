using System;
using System.Drawing;
using System.Net.NetworkInformation;
using System.Windows.Forms;
using SchoolDom.Rfid.Win7.Controls;

namespace SchoolDom.Rfid.Win7
{
    public sealed class MainForm : Form
    {
        // A card held too close to the reader for too long makes some HID readers
        // repeat-fire the same UID several times a second - without this, that
        // would clock the same person in and back out again within the same
        // breath. Ignoring/holding off further scans of the *same* UID for this
        // long (a different person's card is never blocked) fixes it.
        private const int ScanCooldownSeconds = 8;

        private readonly LocalStore _store = new LocalStore();
        private readonly ReaderManager _readerManager = new ReaderManager();
        private readonly SyncService _sync;

        private StatusPill _hidStatusPill;
        private StatusPill _sdkStatusPill;
        private StatusPill _pendingSyncPill;
        private RoundedButton _syncNowButton;
        private CheckBox _globalCaptureToggle;
        private ListView _feedList;
        private Panel _unregisteredBanner;
        private Panel _unregisteredBannerDot;
        private Label _unregisteredBannerLabel;
        private Label _operatorLabel;
        private readonly Timer _bannerTimer = new Timer { Interval = 4000 };
        // Section 3 "background retry mechanism" - flushes the offline queue every
        // 20s regardless of how it got new entries (a scan, or a stalled retry from
        // last tick), so a connection coming back doesn't need a manual nudge. The
        // work itself runs on a background thread (see RunFlush) - it used to run
        // directly on this tick, which froze the whole app ("Not Responding") for
        // up to the 30s HTTP timeout every single time the network was slow, since
        // this timer fires unprompted all day regardless of what the user is doing.
        private readonly Timer _syncTimer = new Timer { Interval = 20000 };
        private int _syncInFlight; // 0/1 guard via Interlocked, so a slow tick can't overlap the next one

        // Root cause of "data stuck / pending sync count never moves": the saved
        // JWT expires (1hr) and SyncService.Request never clears it, so every
        // background tick kept hitting CloudAuthExpiredException and popping
        // ANOTHER LoginForm modal every 20s - easy to miss (e.g. the main window
        // minimized, so the dialog it owns may not surface either), and each
        // miss just guaranteed the identical failure next tick forever. Now:
        // the automatic 20s/network-restored triggers stop nagging with a modal
        // after the first miss and instead leave a banner that doesn't auto-hide
        // until the user acts (Sync Now, which prompts deliberately).
        private bool _authExpiredNeedsAttention;

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
            // Don't auto-retry once a sign-in prompt has already been missed once -
            // see _authExpiredNeedsAttention above. Sync Now (manual: true) always
            // tries regardless, since that's a deliberate user action.
            _syncTimer.Tick += (s, e) => { if (!_authExpiredNeedsAttention) RunFlush(); };
            // "Auto-sync if there's an internet connection" - don't just wait for the
            // next 20s tick once connectivity actually returns; sync right away.
            NetworkChange.NetworkAvailabilityChanged += OnNetworkAvailabilityChanged;

            Load += OnLoad;
            FormClosing += (s, e) =>
            {
                NetworkChange.NetworkAvailabilityChanged -= OnNetworkAvailabilityChanged;
                _readerManager.Dispose();
                _syncTimer.Stop();
            };
        }

        // Fires on a ThreadPool thread already, not the UI thread - safe, since
        // RunFlush's synchronous portion never touches a control directly (the
        // actual UI update it eventually queues is still marshaled the normal way).
        private void OnNetworkAvailabilityChanged(object sender, NetworkAvailabilityEventArgs e)
        {
            if (e.IsAvailable) RunFlush();
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

            // Off the UI thread - on a slow/dead connection this would otherwise
            // freeze the window for up to 30s before the app has even finished
            // opening.
            RunFlush(pullOnly: true);
        }

        private bool PromptSignIn()
        {
            // A ShowDialog owned by a minimized/background window can end up
            // invisible or unfocused on some Windows versions - restore and
            // activate first so the prompt is never silently missed.
            if (WindowState == FormWindowState.Minimized) WindowState = FormWindowState.Normal;
            Show();
            Activate();

            using (var login = new LoginForm(_sync))
            {
                var result = login.ShowDialog(this);
                if (result == DialogResult.OK)
                {
                    _authExpiredNeedsAttention = false;
                    _unregisteredBanner.Visible = false;
                    RefreshOperatorLabel();
                    RefreshPendingSyncCount();
                    return true;
                }
                return false;
            }
        }

        // Runs the network part of a sync pass on a background thread and marshals
        // only the UI update back via BeginInvoke - this is the fix for the app
        // freezing every ~20s. _syncInFlight guards against a slow tick (e.g. a
        // request stuck near its 30s timeout) overlapping the next timer tick and
        // running two of these concurrently.
        private void RunFlush(bool pullOnly = false, bool manual = false)
        {
            if (System.Threading.Interlocked.CompareExchange(ref _syncInFlight, 1, 0) != 0) return;

            if (manual) RunOnUiThreadIfAlive(() => SetSyncNowButtonBusy(true));

            System.Threading.ThreadPool.QueueUserWorkItem(_ =>
            {
                var authExpired = false;
                Exception failure = null;
                FlushResult flushResult = null;
                try
                {
                    if (!pullOnly) flushResult = _sync.FlushPendingQueue();
                    _sync.PullCardAssignments();
                }
                catch (CloudAuthExpiredException)
                {
                    authExpired = true;
                }
                catch (Exception ex)
                {
                    // Network still down, or the server is unreachable - not fatal,
                    // Section 1d's local cache still governs matching; just retry
                    // on the next tick rather than surfacing every transient failure.
                    failure = ex;
                }

                RunOnUiThreadIfAlive(() =>
                {
                    _syncInFlight = 0;
                    RefreshPendingSyncCount();
                    if (manual) SetSyncNowButtonBusy(false);
                    if (flushResult != null) UpdateFeedRowsFromSync(flushResult.Synced);

                    if (authExpired)
                    {
                        if (manual || pullOnly)
                        {
                            // Sync Now, or the very first pull right after opening -
                            // both are already a direct, in-the-moment user action, so
                            // a modal here is expected, not a surprise interruption.
                            _syncTimer.Stop();
                            var signedIn = PromptSignIn();
                            _syncTimer.Start();
                            if (!signedIn) ShowPersistentBanner(AuthExpiredBannerText);
                        }
                        else
                        {
                            // An unattended 20s/network-restored tick - don't pop a
                            // modal the user didn't ask for and may not even see.
                            // Leave an un-missable banner instead; Sync Now (or
                            // reopening the app) is what re-prompts.
                            _authExpiredNeedsAttention = true;
                            ShowPersistentBanner(AuthExpiredBannerText);
                        }
                    }
                    else if (failure != null && (pullOnly || manual))
                    {
                        ShowBanner("Could not sync with the cloud: " + failure.Message, Palette.Gold, Palette.GoldSoft);
                    }
                });
            });
        }

        private void SetSyncNowButtonBusy(bool busy)
        {
            _syncNowButton.Enabled = !busy;
            _syncNowButton.Text = busy ? "Syncing..." : "Sync Now";
        }

        // Section 3 follow-up - "clocked in and clocked out timer": once a queued
        // scan actually makes it to the server, the server (not the desktop app)
        // knows whether it resolved to a clock-in or a clock-out. Match the result
        // back to its feed row by idempotency key and update the label in place.
        private void UpdateFeedRowsFromSync(System.Collections.Generic.List<SyncedScanResult> synced)
        {
            if (synced == null || synced.Count == 0) return;
            foreach (ListViewItem item in _feedList.Items)
            {
                var entry = item.Tag as ScanFeedEntry;
                if (entry == null || string.IsNullOrEmpty(entry.IdempotencyKey)) continue;
                foreach (var result in synced)
                {
                    if (string.Equals(entry.IdempotencyKey, result.IdempotencyKey, StringComparison.OrdinalIgnoreCase))
                    {
                        entry.ClockAction = result.Action;
                        break;
                    }
                }
            }
            _feedList.Invalidate();
        }

        // The form (or its handle) can be gone by the time a background callback
        // completes if the app is closing - guard every marshal-back with this
        // instead of letting BeginInvoke throw into a background thread unhandled.
        private void RunOnUiThreadIfAlive(Action action)
        {
            try
            {
                if (IsDisposed || !IsHandleCreated) return;
                BeginInvoke(action);
            }
            catch (ObjectDisposedException) { }
            catch (InvalidOperationException) { }
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
            sidebar.Controls.Add(BuildNavButton("Attendance History", 242, active: false, onClick: (s, e) => OpenAttendanceHistory()));

            // Fixed position below the nav buttons, NOT Anchor=Bottom - these two
            // controls were completely invisible before (found while adding the
            // Sign Out button: a fresh Panel() defaults to ~100px tall, and Anchor
            // captures its "distance from the bottom edge" against whatever the
            // parent's size is at the moment the control is added - which here is
            // that ~100px default, not the ~700px this sidebar actually ends up
            // once Dock=Left resolves against the Form. Both controls inherited a
            // bogus, deeply-off-screen offset from that mismatch and rendered
            // nowhere - not clipped, not behind anything, just positioned off the
            // visible sidebar entirely). Anchoring to the bottom would need these
            // added after the sidebar itself is parented and Dock has resolved;
            // simplest fix is to just not depend on that ordering at all.
            _operatorLabel = new Label
            {
                Text = "",
                Left = 24,
                Top = 320,
                Width = 200,
                Height = 40,
                Font = Palette.Caption,
                ForeColor = Palette.SoftText
            };
            sidebar.Controls.Add(_operatorLabel);

            // Was a plain LinkLabel - easy to miss against the navy sidebar (small,
            // muted, no visible button shape). A real RoundedButton reads as an
            // actual control instead of blending into the background.
            var signOutButton = RoundedButton.Secondary("Sign Out", 192, 36);
            signOutButton.Left = 24;
            signOutButton.Top = 364;
            signOutButton.Click += (s, e) =>
            {
                _sync.SignOut();
                if (!PromptSignIn()) Application.Exit();
            };
            sidebar.Controls.Add(signOutButton);

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

        private void OpenAttendanceHistory()
        {
            using (var form = new AttendanceHistoryForm(_sync))
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

            // Only meaningful while ShowPersistentBanner's auth-expired message is
            // showing (Cursor.Hand at that point; Cursors.Default otherwise makes
            // this a harmless no-op click for every other banner use).
            EventHandler onBannerClick = (s, e) => { if (_authExpiredNeedsAttention) RunFlush(manual: true); };
            banner.Click += onBannerClick;
            _unregisteredBannerDot.Click += onBannerClick;
            _unregisteredBannerLabel.Click += onBannerClick;

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

            _syncNowButton = RoundedButton.Secondary("Sync Now", 110, 28);
            _syncNowButton.Left = 750;
            _syncNowButton.Top = 68;
            _syncNowButton.Click += (s, e) => RunFlush(manual: true);
            card.Controls.Add(_syncNowButton);

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
            list.Columns.Add("Card UID", 150);
            list.Columns.Add("Person", 230);
            list.Columns.Add("Status", 110);
            list.Columns.Add("Reader", 110);
            list.Columns.Add("Time", 130);

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
                        var dotColor = entry.WasCooldown ? Palette.Gold : entry.Matched ? Palette.Green : Palette.Coral;
                        var dotRect = new Rectangle(e.Bounds.Left + 14, e.Bounds.Top + (e.Bounds.Height - 10) / 2, 10, 10);
                        using (var dotBrush = new SolidBrush(dotColor))
                            e.Graphics.FillEllipse(dotBrush, dotRect);
                        break;
                    case 1:
                        TextRenderer.DrawText(e.Graphics, entry.Uid, Palette.Mono, e.Bounds, Palette.Text,
                            TextFormatFlags.Left | TextFormatFlags.VerticalCenter | TextFormatFlags.LeftAndRightPadding);
                        break;
                    case 2:
                        var name = entry.WasCooldown ? "Already scanned - cooling off" : entry.Matched ? entry.PersonName : "Unregistered card";
                        var color = entry.WasCooldown ? Palette.Gold : entry.Matched ? Palette.Text : Palette.Coral;
                        TextRenderer.DrawText(e.Graphics, name, Palette.BodyBold, e.Bounds, color,
                            TextFormatFlags.Left | TextFormatFlags.VerticalCenter | TextFormatFlags.LeftAndRightPadding);
                        break;
                    case 3:
                        string statusText;
                        Color statusColor;
                        if (entry.WasCooldown || !entry.Matched) { statusText = ""; statusColor = Palette.Muted; }
                        else if (entry.ClockAction == "clock_in") { statusText = "Clocked In"; statusColor = Palette.Green; }
                        else if (entry.ClockAction == "clock_out") { statusText = "Clocked Out"; statusColor = Palette.Gold; }
                        else { statusText = "Pending sync"; statusColor = Palette.Muted; }
                        TextRenderer.DrawText(e.Graphics, statusText, Palette.Caption, e.Bounds, statusColor,
                            TextFormatFlags.Left | TextFormatFlags.VerticalCenter | TextFormatFlags.LeftAndRightPadding);
                        break;
                    case 4:
                        TextRenderer.DrawText(e.Graphics, entry.SourceReaderName, Palette.Caption, e.Bounds, Palette.Muted,
                            TextFormatFlags.Left | TextFormatFlags.VerticalCenter | TextFormatFlags.LeftAndRightPadding);
                        break;
                    case 5:
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

            var cooldownRemaining = _store.SecondsUntilCooldownClears(e.Uid, ScanCooldownSeconds);
            if (cooldownRemaining > 0)
            {
                PrependFeedEntry(new ScanFeedEntry
                {
                    ScannedAtLocal = e.ScannedAtUtc.ToLocalTime(),
                    Uid = e.Uid,
                    WasCooldown = true,
                    SourceReaderType = e.SourceReaderType,
                    SourceReaderName = e.SourceReaderName
                });
                ShowCooldownCountdown(e.Uid, cooldownRemaining);
                return;
            }
            _store.RecordScanForCooldown(e.Uid);

            var assignment = _store.FindActiveAssignment(e.Uid);
            var idempotencyKey = assignment != null ? Guid.NewGuid().ToString("N") : null;
            var entry = new ScanFeedEntry
            {
                ScannedAtLocal = e.ScannedAtUtc.ToLocalTime(),
                Uid = e.Uid,
                Matched = assignment != null,
                PersonName = assignment != null ? assignment.PersonName : null,
                SourceReaderType = e.SourceReaderType,
                SourceReaderName = e.SourceReaderName,
                IdempotencyKey = idempotencyKey
            };
            PrependFeedEntry(entry);

            if (assignment != null)
            {
                _store.EnqueuePendingAttendance(new PendingAttendanceRecord
                {
                    IdempotencyKey = idempotencyKey,
                    CardUid = e.Uid,
                    PersonId = assignment.PersonId,
                    ScannedAtUtc = e.ScannedAtUtc.ToString("o"),
                    ReaderType = e.SourceReaderType.ToString(),
                    ReaderName = e.SourceReaderName
                });
                RefreshPendingSyncCount();
            }
            else
            {
                ShowBanner("Unregistered card scanned: " + e.Uid + " — not linked to anyone.", Palette.Coral, Palette.CoralSoft);
            }
        }

        // A live-ticking "wait 8s..." banner instead of a static message, so it's
        // obvious the second scan wasn't just silently ignored/dropped. Manages the
        // banner's visibility itself (stopping/restarting _bannerTimer each tick) -
        // otherwise the unrelated 4s auto-hide would cut the countdown off partway
        // through whenever the cooldown is longer than 4 seconds.
        private void ShowCooldownCountdown(string cardUid, int initialSeconds)
        {
            var remaining = initialSeconds;
            _bannerTimer.Stop();
            ShowCooldownBannerText(cardUid, remaining);
            _unregisteredBanner.Visible = true;

            var countdownTimer = new Timer { Interval = 1000 };
            countdownTimer.Tick += (s, e) =>
            {
                remaining--;
                if (remaining <= 0)
                {
                    countdownTimer.Stop();
                    countdownTimer.Dispose();
                    _unregisteredBanner.Visible = false;
                    return;
                }
                ShowCooldownBannerText(cardUid, remaining);
            };
            countdownTimer.Start();
        }

        private void ShowCooldownBannerText(string cardUid, int remainingSeconds)
        {
            _unregisteredBannerLabel.Text = "Card " + cardUid + " already scanned - cooling off for " + remainingSeconds + "s to avoid a duplicate.";
            _unregisteredBannerLabel.ForeColor = Palette.Gold;
            _unregisteredBannerDot.BackColor = Palette.Gold;
            _unregisteredBanner.BackColor = Palette.GoldSoft;
        }

        private void PrependFeedEntry(ScanFeedEntry entry)
        {
            var item = new ListViewItem(new[] { "", entry.Uid, "", "", "", "" }) { Tag = entry };
            _feedList.Items.Insert(0, item);
            while (_feedList.Items.Count > 200) _feedList.Items.RemoveAt(_feedList.Items.Count - 1);
        }

        private void RefreshPendingSyncCount()
        {
            var count = _store.PendingAttendanceCount();
            if (count == 0)
                _pendingSyncPill.SetState("0 pending sync", Palette.Muted, Palette.LightButton);
            else
                _pendingSyncPill.SetState(count + " pending sync", Palette.Gold, Palette.GoldSoft);
        }

        private void ShowBanner(string message, Color accent, Color tint)
        {
            _unregisteredBanner.Cursor = Cursors.Default;
            _unregisteredBannerLabel.Text = message;
            _unregisteredBannerLabel.ForeColor = accent;
            _unregisteredBannerDot.BackColor = accent;
            _unregisteredBanner.BackColor = tint;
            _unregisteredBanner.Visible = true;
            _bannerTimer.Stop();
            _bannerTimer.Start();
        }

        private const string AuthExpiredBannerText = "Sign-in expired - nothing is syncing. Click here, or Sync Now, to sign in again.";

        // Doesn't auto-hide via _bannerTimer (unlike ShowBanner) and is clickable -
        // used specifically for "sync can't proceed until you do something",
        // which a message that quietly vanishes after 4s would undercut.
        private void ShowPersistentBanner(string message)
        {
            _bannerTimer.Stop();
            _unregisteredBannerLabel.Text = message;
            _unregisteredBannerLabel.ForeColor = Palette.Coral;
            _unregisteredBannerDot.BackColor = Palette.Coral;
            _unregisteredBanner.BackColor = Palette.CoralSoft;
            _unregisteredBanner.Cursor = Cursors.Hand;
            _unregisteredBanner.Visible = true;
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
