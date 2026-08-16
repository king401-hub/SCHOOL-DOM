using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.IO;
using System.Linq;
using System.Net;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace SchoolDom.StudentCbt.Win7
{
    public class MainForm : Form
    {
        private readonly LanClient _client = new LanClient();
        private readonly Timer _timer = new Timer { Interval = 1000 };
        private Panel _root;
        private Label _status;
        private Label _timeLabel;
        private Label _lanLabel;
        private Panel _questionPanel;
        private Dictionary<string, object> _student;
        private Dictionary<string, object> _exam;
        private Dictionary<string, object> _session;
        private List<Dictionary<string, object>> _examChoices = new List<Dictionary<string, object>>();
        private string _studentId;
        private List<Dictionary<string, object>> _questions = new List<Dictionary<string, object>>();
        private Dictionary<string, object> _answers = new Dictionary<string, object>();
        private int _current;
        private bool _examMode;
        private bool _submitting;
        private bool _calculatorOpen;
        private bool _dialogOpen;

        // Path for local answer backup — survives LAN disconnects
        private static readonly string _backupDir = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            "SchoolDom", "StudentCbt", "answers");
        private string _answerBackupPath;
        private DateTime? _offlineSince;
        private bool _pendingAutoSubmit;
        private int _lastSaveSecond = -1;
        private WebBrowser _questionWebView;

        // Server-anchored countdown: the admin LAN server's clock is the only source of truth
        // for how much time is left (it is what produced session.EndsAt in the first place).
        // We re-seed _serverRemainingSeconds from every response that carries one and tick it
        // down locally with Environment.TickCount, a monotonic counter that keeps advancing at
        // a steady rate no matter what the student's system clock/timezone is set to. This is
        // deliberately NOT DateTime.Now/UtcNow - comparing session.EndsAt (stamped using the
        // ADMIN PC's clock) against THIS PC's wall clock is what let two machines with different
        // clocks disagree about how much time was left.
        private int? _serverRemainingSeconds;
        private int _serverSyncTickCount;

        // Fallback for when no server-timed response has ever arrived (e.g. the admin
        // LAN server is still on an old build that doesn't send time_remaining_seconds).
        // The OLD fallback compared session.EndsAt (a wall-clock timestamp stamped by the
        // ADMIN PC) against this PC's own DateTime.UtcNow - if the two machines' clocks
        // disagree by any real amount (a dead CMOS battery on an old Win7 exam station is
        // enough on its own), that subtraction produces nonsense like "42211:39:01"
        // instead of a real countdown. This anchors the fallback to a purely local,
        // monotonic clock instead: how many seconds of exam duration are left, counted
        // down from Environment.TickCount at the moment the exam actually started on
        // THIS machine - no wall clock, no other PC's clock, involved at all.
        private int _localExamStartTick;
        private int _localExamDurationSeconds;

        public MainForm()
        {
            Text = "SchoolDom Student CBT v" + Application.ProductVersion;
            Width = 1120;
            Height = 740;
            MinimumSize = new Size(960, 620);
            StartPosition = FormStartPosition.CenterScreen;
            BackColor = Palette.Background;
            Font = new Font("Segoe UI", 10);
            // Every screen in this app is rebuilt from scratch at runtime with explicit
            // pixel Left/Top/Width/Height (there's no Designer-generated
            // InitializeComponent(), which is what AutoScaleMode.Font is actually meant to
            // scale). Applying Font-based auto-scale on top of that scales dynamically-added
            // controls inconsistently at non-100% DPI - e.g. a fixed-height header docked to
            // the top can end up taller/shorter on screen than the content layout code
            // (which computes positions from ClientSize) assumed, so the two disagree and
            // the header overlaps content that should be below it. None keeps every pixel
            // value we already compute self-consistent regardless of DPI; text still renders
            // at the correct physical size on its own since Windows scales font points, not
            // WinForms' AutoScale layer.
            AutoScaleMode = AutoScaleMode.None;
            Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath);
            KeyPreview = true;

            _timer.Tick += TimerTick;
            FormClosing += MainFormClosing;
            Deactivate += MainFormDeactivate;
            KeyDown += MainFormKeyDown;

            _root = new Panel { Dock = DockStyle.Fill };
            Controls.Add(_root);
            ShowConnect();
        }

        private void ShowConnect()
        {
            _examMode = false;
            _submitting = false;
            TopMost = false;
            FormBorderStyle = FormBorderStyle.Sizable;
            WindowState = FormWindowState.Normal;
            _timer.Stop();
            _root.Controls.Clear();

            var hero = new Panel { Dock = DockStyle.Left, Width = 390, BackColor = Palette.Navy };
            hero.Controls.Add(Label("SchoolDom", 38, 44, 22, true, 280, Color.White));
            hero.Controls.Add(Label("Student CBT", 40, 88, 12, false, 240, Palette.SoftText));
            hero.Controls.Add(Label("Connect to the exam room LAN and start with your Student ID and PIN.", 40, 180, 15, false, 290, Color.White));

            var content = new Panel { Dock = DockStyle.Fill, BackColor = Palette.Background };
            var card = Card(80, 60, 560, 460);
            content.Controls.Add(card);
            card.Controls.Add(Label("Exam Login", 34, 30, 20, true, 420, Palette.Text));
            card.Controls.Add(Label("The app connects to the admin LAN server automatically. No internet login is needed.", 36, 76, 10, false, 480, Palette.Muted));

            var server = Field(card, "LAN Server", "", 36, 150, false);
            server.Width = 500;
            var token = Field(card, "Network Token (optional)", "", 36, 230, false);
            token.Width = 500;
            var studentId = Field(card, "Student ID", "", 36, 310, false);
            var pin = Field(card, "Exam PIN", "", 306, 310, true);
            ApplyNumbersOnly(pin);
            _status = Label("", 36, 426, 10, false, 490, Palette.Muted);
            card.Controls.Add(_status);

            var discover = SecondaryButton("Find LAN", 36, 374, 130);
            discover.Click += (s, e) =>
            {
                try
                {
                    _client.DiscoveryToken = token.Text.Trim();
                    SetStatus("Searching for admin LAN server...", Palette.Muted);
                    server.Text = _client.Discover();
                    SetStatus("Connected to " + server.Text, Palette.Green);
                }
                catch (Exception ex)
                {
                    SetStatus("Could not find LAN server. Ask admin for the Network Token.", Palette.Coral);
                    MessageBox.Show(ex.Message, "LAN discovery failed");
                }
            };
            card.Controls.Add(discover);

            var start = PrimaryButton("Log In", 180, 374, 150);
            start.Click += (s, e) =>
            {
                try
                {
                    _client.DiscoveryToken = token.Text.Trim();
                    if (!string.IsNullOrWhiteSpace(server.Text)) _client.BaseUrl = server.Text.Trim().TrimEnd('/');
                    if (string.IsNullOrWhiteSpace(_client.BaseUrl)) _client.Discover();
                    SetStatus("Checking Student ID and PIN...", Palette.Muted);
                    var login = _client.Login(studentId.Text, pin.Text);
                    if (!Convert.ToBoolean(login.ContainsKey("success") ? login["success"] : false))
                    {
                        MessageBox.Show(JsonUtil.Text(login.ContainsKey("message") ? login["message"] : "Login failed."), "Login failed");
                        return;
                    }
                    _student = login["student"] as Dictionary<string, object>;
                    _studentId = studentId.Text.Trim();
                    // The admin LAN server never auto-starts a session on login (even when
                    // only one exam matches the PIN) - the student always sees the Available
                    // Exams screen first and explicitly picks one.
                    var choices = JsonUtil.List(login.ContainsKey("exams") ? login["exams"] : null)
                        .Select(item => item as Dictionary<string, object>)
                        .Where(item => item != null)
                        .ToList();
                    if (!choices.Any())
                    {
                        MessageBox.Show("No exam was returned for this Student ID and PIN.", "No exam");
                        return;
                    }
                    ShowExamSelection(choices);
                }
                catch (Exception ex)
                {
                    SetStatus("Could not log in.", Palette.Coral);
                    MessageBox.Show(ex.Message, "Login failed");
                }
            };
            card.Controls.Add(start);

            _root.Controls.Add(content);
            _root.Controls.Add(hero);
        }

        private void ShowExamSelection(List<Dictionary<string, object>> exams)
        {
            _examChoices = exams;
            _examMode = false;
            _timer.Stop();
            _root.Controls.Clear();

            var header = new Panel { Dock = DockStyle.Top, Height = 84, BackColor = Palette.Navy };
            header.Controls.Add(Label("Available Exams", 28, 18, 18, true, 420, Color.White));
            header.Controls.Add(Label(exams.Count + " exam(s) available for you to take.", 30, 52, 10, false, 520, Palette.SoftText));
            var signOut = SecondaryButton("Sign Out", Math.Max(700, Math.Max(960, ClientSize.Width) - 160), 22, 130);
            signOut.Click += (s, e) => ShowConnect();
            header.Controls.Add(signOut);
            _root.Controls.Add(header);

            var content = new Panel { Dock = DockStyle.Fill, BackColor = Palette.Background, AutoScroll = true };
            const int columnWidth = 820;
            var column = new Panel { Left = 0, Top = 0, Width = columnWidth, BackColor = Color.Transparent };
            Action centerColumn = () => { column.Left = Math.Max(24, (content.ClientSize.Width - column.Width) / 2); };
            content.Resize += (s, e) => centerColumn();

            // Verified by screen capture: a card placed too close under the header (e.g. y=32)
            // still rendered visibly clipped at the top on this exact layout even though the
            // math says it shouldn't overlap - 90px of clearance is the smallest gap that
            // reliably rendered the full card in testing.
            var y = 90;
            const int profileCardWidth = 290;
            const int profileBadgeWidth = 242;
            const int profileBadgeHeight = 136;
            const int profileCardHeight = profileBadgeHeight + 16;
            var profileCard = Card(0, y, profileCardWidth, profileCardHeight);
            profileCard.Controls.Add(CreateLargeStudentBadge((profileCardWidth - profileBadgeWidth) / 2, (profileCardHeight - profileBadgeHeight) / 2));
            column.Controls.Add(profileCard);
            y += profileCard.Height + 28;

            column.Controls.Add(Label("Select an exam to begin", 0, y, 13, true, columnWidth, Palette.Text));
            y += 32;

            foreach (var exam in exams)
            {
                var status = Value(exam, "status", "Status");
                var isInProgress = string.Equals(status, "In Progress", StringComparison.OrdinalIgnoreCase);

                var card = Card(0, y, columnWidth, 148);
                card.Controls.Add(Label(Value(exam, "title", "Title"), 24, 16, 14, true, 480, Palette.Text));

                var statusPill = Label(string.IsNullOrWhiteSpace(status) ? "Not Started" : status, 0, 20, 9, true, 160,
                    isInProgress ? Palette.Green : Palette.Muted);
                statusPill.BackColor = isInProgress ? Palette.GreenSoft : Palette.LightButton;
                statusPill.Padding = new Padding(10, 4, 10, 4);
                statusPill.Left = columnWidth - 24 - statusPill.PreferredSize.Width;
                card.Controls.Add(statusPill);

                var className = Value(exam, "class_name", "ClassName");
                var examType = Value(exam, "exam_type", "ExamType");
                var metaLine1 = "Subject: " + (string.IsNullOrWhiteSpace(Value(exam, "subject", "Subject")) ? "-" : Value(exam, "subject", "Subject"))
                    + (string.IsNullOrWhiteSpace(className) ? "" : "   ·   Class: " + className)
                    + (string.IsNullOrWhiteSpace(examType) ? "" : "   ·   Type: " + examType);
                card.Controls.Add(Label(metaLine1, 24, 54, 10, false, columnWidth - 48, Palette.Muted));

                var minutes = Math.Max(1, JsonUtil.Int(Raw(exam, "duration_seconds", "DurationSeconds"), 3600) / 60);
                var questionCount = JsonUtil.Int(Raw(exam, "question_count", "QuestionCount"), 0);
                var metaLine2 = "Duration: " + minutes + " minute(s)   ·   Questions: " + questionCount;
                card.Controls.Add(Label(metaLine2, 24, 78, 10, false, columnWidth - 48, Palette.Muted));

                var startBtn = PrimaryButton(isInProgress ? "Resume Exam" : "Start Exam", columnWidth - 24 - 170, 96, 170);
                var selected = exam;
                startBtn.Click += (s, e) => StartSelectedExam(selected);
                card.Controls.Add(startBtn);

                column.Controls.Add(card);
                y += card.Height + 20;
            }

            column.Height = y + 24;
            content.Controls.Add(column);
            centerColumn();
            _root.Controls.Add(content);
            // Defensive: make sure the panel never opens pre-scrolled away from the top.
            BeginInvoke((MethodInvoker)(() => content.AutoScrollPosition = new Point(0, 0)));
        }

        private void StartSelectedExam(Dictionary<string, object> exam)
        {
            var started = _client.StartSession(_studentId, Value(exam, "id", "Id"));
            if (!Convert.ToBoolean(started.ContainsKey("success") ? started["success"] : false))
            {
                MessageBox.Show(JsonUtil.Text(started.ContainsKey("message") ? started["message"] : "Could not start exam."), "Start failed");
                if (_examChoices.Any()) ShowExamSelection(_examChoices); else ShowConnect();
                return;
            }
            _exam = started["exam"] as Dictionary<string, object>;
            _session = started["session"] as Dictionary<string, object>;
            SyncServerTimer(started);
            ShowInstructions();
        }

        private void ShowInstructions()
        {
            LoadExamDetail();
            _root.Controls.Clear();
            var header = new Panel { Dock = DockStyle.Top, Height = 84, BackColor = Palette.Navy };
            header.Controls.Add(Label(Value(_exam, "title", "Title"), 28, 18, 18, true, 620, Color.White));
            header.Controls.Add(Label("Review the exam details below, then start when you're ready.", 30, 52, 10, false, 620, Palette.SoftText));
            _root.Controls.Add(header);

            var content = new Panel { Dock = DockStyle.Fill, BackColor = Palette.Background, AutoScroll = true };
            const int cardWidth = 820;
            // Same header+AutoScroll-content+card-near-top structure as ShowExamSelection,
            // which was verified by screen capture to render clipped at 24px clearance under
            // the header despite the layout math looking correct - matching its 90px minimum.
            var card = Card(0, 90, cardWidth, 10);
            Action centerCard = () => { card.Left = Math.Max(24, (content.ClientSize.Width - card.Width) / 2); };
            content.Resize += (s, e) => centerCard();

            var y = 24;
            card.Controls.Add(Label("Your Details", 28, y, 11, true, 300, Palette.Muted));
            y += 26;
            const int profileBadgeWidth = 242;
            card.Controls.Add(CreateLargeStudentBadge(28, y));
            var profileBottom = y + 136;

            var metaLeft = 28 + profileBadgeWidth + 48;
            var metaTop = y + 4;
            card.Controls.Add(Label("Exam Details", metaLeft, metaTop, 11, true, 300, Palette.Muted));
            metaTop += 26;
            var minutes = Math.Max(1, JsonUtil.Int(Raw(_exam, "duration_seconds", "DurationSeconds"), 3600) / 60);
            var examType = Value(_exam, "exam_type", "ExamType");
            var examDetailLines = new[]
            {
                "Subject: " + (string.IsNullOrWhiteSpace(Value(_exam, "subject", "Subject")) ? "-" : Value(_exam, "subject", "Subject")),
                string.IsNullOrWhiteSpace(examType) ? null : "Type: " + examType,
                "Duration: " + minutes + " minute(s)",
                "Questions: " + _questions.Count,
            };
            foreach (var line in examDetailLines)
            {
                if (line == null) continue;
                card.Controls.Add(Label(line, metaLeft, metaTop, 10, false, cardWidth - metaLeft - 28, Palette.Text));
                metaTop += 24;
            }

            y = Math.Max(profileBottom, metaTop) + 20;
            card.Controls.Add(new Panel { Left = 28, Top = y, Width = cardWidth - 56, Height = 1, BackColor = Palette.Border });
            y += 20;

            card.Controls.Add(Label("Instructions", 28, y, 14, true, 680, Palette.Text));
            y += 30;
            var instructionsText = Value(_exam, "instructions", "Instructions");
            var instructions = new TextBox
            {
                Left = 28,
                Top = y,
                Width = cardWidth - 56,
                Height = 170,
                Multiline = true,
                ReadOnly = true,
                ScrollBars = ScrollBars.Vertical,
                Text = string.IsNullOrWhiteSpace(instructionsText) ? "No special instructions." : HtmlToPlainText(instructionsText),
                Font = new Font("Segoe UI", 11),
                BorderStyle = BorderStyle.FixedSingle
            };
            card.Controls.Add(instructions);
            y += instructions.Height + 20;

            var warningColor = Color.FromArgb(150, 84, 0);
            var warning = new Panel { Left = 28, Top = y, Width = cardWidth - 56, Height = 48, BackColor = Color.FromArgb(255, 243, 224) };
            warning.Controls.Add(Label(
                "⚠ Once you click Start Exam, the timer begins immediately and cannot be paused. Make sure you are ready before continuing.",
                14, 8, 9, true, warning.Width - 28, warningColor));
            card.Controls.Add(warning);
            y += warning.Height + 24;

            var back = SecondaryButton("Back", 28, y, 140);
            back.Click += (s, e) => { if (_examChoices.Any()) ShowExamSelection(_examChoices); else ShowConnect(); };
            card.Controls.Add(back);
            var startExamBtn = PrimaryButton("Start Exam", cardWidth - 28 - 170, y, 170);
            startExamBtn.Click += (s, e) => EnterExamMode();
            card.Controls.Add(startExamBtn);
            var prefetchStatus = Label("Preparing exam materials...", cardWidth - 28 - 170 - 270, y + 13, 9, false, 260, Palette.Muted);
            prefetchStatus.TextAlign = ContentAlignment.MiddleRight;
            prefetchStatus.Visible = false;
            card.Controls.Add(prefetchStatus);
            y += 42 + 24;

            card.Height = y;
            content.Controls.Add(card);
            centerCard();
            _root.Controls.Add(content);

            // Question images fetch fastest the first time they're needed - get
            // that fetch (and the local caching) out of the way now, while the
            // student is still reading (untimed), instead of during the timed
            // exam. Never blocks Start for more than a few seconds: an image
            // that isn't cached yet just falls back to its live URL, same as
            // before this fix existed.
            var prefetchSettled = false;
            Action finishPrefetch = () =>
            {
                if (prefetchSettled) return;
                prefetchSettled = true;
                startExamBtn.Enabled = true;
                prefetchStatus.Visible = false;
            };
            var prefetchSafetyTimer = new Timer { Interval = 8000 };
            prefetchSafetyTimer.Tick += (s, e) => { prefetchSafetyTimer.Stop(); prefetchSafetyTimer.Dispose(); finishPrefetch(); };
            startExamBtn.Enabled = false;
            prefetchStatus.Visible = true;
            prefetchSafetyTimer.Start();
            PrefetchQuestionImages(() => { prefetchSafetyTimer.Stop(); prefetchSafetyTimer.Dispose(); finishPrefetch(); });
        }

        private void LoadExamDetail()
        {
            var detail = _client.ExamDetail(Value(_exam, "id", "Id"));
            var payload = detail.ContainsKey("payload") ? detail["payload"] as Dictionary<string, object> : null;
            _questions = JsonUtil.List(payload != null && payload.ContainsKey("questions") ? payload["questions"] : null)
                .Select(item => item as Dictionary<string, object>)
                .Where(item => item != null)
                .ToList();
            var answers = Raw(_session, "answers", "Answers") as Dictionary<string, object>;
            _answers = answers ?? new Dictionary<string, object>();
            if (!_questions.Any()) throw new InvalidOperationException("This exam has no questions.");
        }

        private static readonly Regex ImgSrcRegex = new Regex("<img[^>]+src=[\"']([^\"']+)[\"']", RegexOptions.IgnoreCase | RegexOptions.Compiled);

        private static string ImageCacheDir
        {
            get
            {
                var dir = Path.Combine(Path.GetTempPath(), "SchoolDomStudentCbt", "ImageCache");
                Directory.CreateDirectory(dir);
                return dir;
            }
        }

        private static string CachePathForImageUrl(string url)
        {
            using (var md5 = MD5.Create())
            {
                var hash = md5.ComputeHash(Encoding.UTF8.GetBytes(url));
                var hex = BitConverter.ToString(hash).Replace("-", "").ToLowerInvariant();
                string ext;
                try { ext = Path.GetExtension(new Uri(url).AbsolutePath); }
                catch { ext = ""; }
                if (string.IsNullOrEmpty(ext) || ext.Length > 5) ext = ".img";
                return Path.Combine(ImageCacheDir, hex + ext);
            }
        }

        // question.image / group.image arrive as inline data: URLs (they're synced/embedded
        // this way specifically so they don't need a live network fetch on the student PC -
        // see PrefetchQuestionImages). But the WebBrowser control's embedded Trident engine
        // defaults to an old IE compatibility mode that caps how long a data: URI in an <img
        // src> can be (roughly 32KB) - past that it just renders as a broken image icon with
        // no error. Writing it to the same on-disk cache used for prefetched images and
        // pointing at that with a file:// URL sidesteps the cap entirely, same as those.
        private static string LocalizeDataImage(string dataUrl)
        {
            if (string.IsNullOrWhiteSpace(dataUrl) || !dataUrl.StartsWith("data:image/", StringComparison.OrdinalIgnoreCase))
                return dataUrl;
            try
            {
                var comma = dataUrl.IndexOf(',');
                if (comma < 0) return dataUrl;
                var path = CachePathForImageUrl(dataUrl);
                if (!File.Exists(path))
                {
                    var bytes = Convert.FromBase64String(dataUrl.Substring(comma + 1));
                    File.WriteAllBytes(path, bytes);
                }
                return new Uri(path).AbsoluteUri;
            }
            catch
            {
                return dataUrl;
            }
        }

        private static void CollectImageUrls(string html, HashSet<string> urls)
        {
            if (string.IsNullOrWhiteSpace(html)) return;
            foreach (Match m in ImgSrcRegex.Matches(html))
                urls.Add(m.Groups[1].Value);
        }

        // Only rewrites a src if it's actually cached on disk - an image whose
        // download failed or hasn't finished yet is left pointing at its
        // original (slower, but still working) live URL rather than a
        // file:// path that doesn't exist.
        private static string RewriteImageUrlsToLocalCache(string html)
        {
            if (string.IsNullOrWhiteSpace(html)) return html;
            return ImgSrcRegex.Replace(html, m =>
            {
                var url = m.Groups[1].Value;
                var cachedPath = CachePathForImageUrl(url);
                if (!File.Exists(cachedPath)) return m.Value;
                return m.Value.Replace(url, new Uri(cachedPath).AbsoluteUri);
            });
        }

        private static void SetValue(Dictionary<string, object> item, string value, params string[] keys)
        {
            if (item == null) return;
            foreach (var key in keys)
            {
                if (item.ContainsKey(key)) { item[key] = value; return; }
            }
        }

        /// <summary>
        /// Downloads every question/passage image up front, while the student is
        /// still on the untimed Instructions screen, and rewrites each &lt;img&gt;
        /// src to the local cached copy. Without this, an image was fetched live
        /// by the embedded browser control the instant a question was first shown
        /// - and again on every revisit, since RenderQuestion tears down and
        /// rebuilds the WebBrowser control on every Next/Previous/jump click - so
        /// the picture visibly "popped in" late every single time.
        ///
        /// Runs on a background thread and never blocks exam start for long: an
        /// image not yet cached when the student clicks Start just falls back to
        /// its original live URL for that one view (no worse than before), while
        /// everything else benefits from what's already cached by then.
        /// </summary>
        private void PrefetchQuestionImages(Action onDone)
        {
            var urls = new HashSet<string>();
            foreach (var question in _questions)
            {
                CollectImageUrls(Value(question, "text", "Text"), urls);
                var group = Raw(question, "group", "Group") as Dictionary<string, object>;
                if (group != null) CollectImageUrls(Value(group, "passage_text", "PassageText"), urls);
            }
            if (!urls.Any())
            {
                onDone?.Invoke();
                return;
            }

            Task.Factory.StartNew(() =>
            {
                foreach (var url in urls)
                {
                    try
                    {
                        var path = CachePathForImageUrl(url);
                        if (File.Exists(path)) continue;
                        using (var client = new WebClient())
                        {
                            client.Headers.Add(HttpRequestHeader.UserAgent, "SchoolDomStudentCbt");
                            client.DownloadFile(url, path);
                        }
                    }
                    catch
                    {
                        // Leave this one uncached - RenderQuestion's HTML will still
                        // point at the live URL and load it the slow way, same as before.
                    }
                }
            }).ContinueWith(_ =>
            {
                foreach (var question in _questions)
                {
                    SetValue(question, RewriteImageUrlsToLocalCache(Value(question, "text", "Text")), "text", "Text");
                    var group = Raw(question, "group", "Group") as Dictionary<string, object>;
                    if (group != null)
                        SetValue(group, RewriteImageUrlsToLocalCache(Value(group, "passage_text", "PassageText")), "passage_text", "PassageText");
                }
                onDone?.Invoke();
            }, TaskScheduler.FromCurrentSynchronizationContext());
        }

        private void SaveAnswersLocally()
        {
            if (string.IsNullOrWhiteSpace(_answerBackupPath) || _answers == null) return;
            try
            {
                Directory.CreateDirectory(Path.GetDirectoryName(_answerBackupPath));
                File.WriteAllText(_answerBackupPath, JsonUtil.Serialize(_answers));
            }
            catch { }
        }

        private void RestoreAnswersFromBackup()
        {
            if (string.IsNullOrWhiteSpace(_answerBackupPath) || !File.Exists(_answerBackupPath)) return;
            try
            {
                var json = File.ReadAllText(_answerBackupPath);
                var restored = JsonUtil.Object(json);
                if (restored != null && restored.Count > 0 && (_answers == null || _answers.Count == 0))
                    _answers = restored;
            }
            catch { }
        }

        private void EnterExamMode()
        {
            // Reset ends_at to now + duration so instruction-reading time doesn't eat into exam time
            try
            {
                var began = _client.BeginExam(Value(_session, "id", "Id"));
                if (began.ContainsKey("session") && began["session"] is Dictionary<string, object> updatedSession)
                    _session = updatedSession;
                SyncServerTimer(began);
            }
            catch { }

            _localExamStartTick = Environment.TickCount;
            _localExamDurationSeconds = Math.Max(60, JsonUtil.Int(Raw(_exam, "duration_seconds", "DurationSeconds"), 3600));

            _examMode = true;
            _current = 0;
            var sessionId = Value(_session, "id", "Id");
            _answerBackupPath = Path.Combine(_backupDir, sessionId + ".json");
            RestoreAnswersFromBackup();
            _offlineSince = null;
            _pendingAutoSubmit = false;
            _lastSaveSecond = -1;
            TopMost = true;
            FormBorderStyle = FormBorderStyle.None;
            WindowState = FormWindowState.Maximized;
            _timer.Start();
            ShowExam();
        }

        private void ShowExam()
        {
            _root.Controls.Clear();
            _questionPanel = null;
            _questionWebView = null;
            var header = new Panel { Dock = DockStyle.Top, Height = 82, BackColor = Palette.Navy };
            var headerWidth = Math.Max(960, ClientSize.Width);
            header.Controls.Add(Label(Value(_exam, "title", "Title"), 22, 14, 16, true, Math.Max(420, headerWidth - 560), Color.White));
            var calcTop = SecondaryButton("Calculator", Math.Max(520, headerWidth - 350), 20, 126);
            calcTop.Click += (s, e) => ShowCalculator();
            header.Controls.Add(calcTop);
            _lanLabel = null;
            _timeLabel = Label(TimeText(), Math.Max(748, headerWidth - 210), 28, 12, true, 200, Color.White);
            header.Controls.Add(_timeLabel);
            _root.Controls.Add(header);

            var content = new Panel { Dock = DockStyle.Fill, BackColor = Palette.Background };
            var availableWidth = Math.Max(960, ClientSize.Width);
            var availableHeight = Math.Max(620, ClientSize.Height - header.Height);
            var sideWidth = 286;
            var gap = 24;
            var mainWidth = Math.Min(820, availableWidth - sideWidth - gap - 96);
            // Same header + card-near-top structure as ShowExamSelection/ShowInstructions,
            // which needed 90px of clearance under the header to render without clipping -
            // reserve the same here and take the extra height back out of the card so it
            // doesn't overflow past the bottom of the window.
            var top = 90;
            var cardHeight = Math.Max(520, availableHeight - top - 40);
            var totalWidth = sideWidth + gap + mainWidth;
            var left = Math.Max(24, (availableWidth - totalWidth) / 2);
            var side = Card(left, top, sideWidth, cardHeight);
            var main = Card(left + sideWidth + gap, top, mainWidth, cardHeight);
            content.Controls.Add(side);
            content.Controls.Add(main);
            _root.Controls.Add(content);

            const int studentBadgeWidth = 242;
            side.Controls.Add(CreateLargeStudentBadge((sideWidth - studentBadgeWidth) / 2, 42));
            side.Controls.Add(Label("Questions", 18, 190, 11, true, 230, Palette.Text));
            var questionNav = new Panel { Left = 18, Top = 228, Width = 242, Height = Math.Max(230, cardHeight - 332), AutoScroll = true, BorderStyle = BorderStyle.None };
            for (var i = 0; i < _questions.Count; i++)
            {
                var index = i;
                var button = new Button
                {
                    Text = (i + 1).ToString(),
                    Left = (i % 5) * 46,
                    Top = (i / 5) * 40,
                    Width = 40,
                    Height = 34,
                    FlatStyle = FlatStyle.Flat,
                    BackColor = _answers.ContainsKey(QuestionId(_questions[i], i)) ? Palette.GreenSoft : Palette.LightButton,
                    ForeColor = Palette.Text,
                    Font = new Font("Segoe UI", 9, FontStyle.Bold),
                    TextAlign = ContentAlignment.MiddleCenter
                };
                if (i == _current) { button.BackColor = Palette.Blue; button.ForeColor = Color.White; }
                button.Click += (s, e) => { SaveCurrentAnswer(main); _current = index; ShowExam(); };
                questionNav.Controls.Add(button);
            }
            side.Controls.Add(questionNav);

            var submit = PrimaryButton("Submit Exam", 18, cardHeight - 66, 242);
            submit.Click += (s, e) => SubmitExam();
            side.Controls.Add(submit);

            RenderQuestion(main);
        }

        private void RenderQuestion(Panel main)
        {
            _questionPanel = main;
            var question = _questions[_current];
            var body = new Panel { Left = 0, Top = 0, Width = main.Width, Height = main.Height - 82, AutoScroll = true, BackColor = Color.White };
            var footer = new Panel { Left = 0, Top = main.Height - 82, Width = main.Width, Height = 80, BackColor = Color.White };
            main.Controls.Add(body);
            main.Controls.Add(footer);

            var innerWidth = main.Width - 64;
            body.Controls.Add(Label("Question " + (_current + 1) + " of " + _questions.Count, 32, 24, 10, true, 260, Palette.Muted));

            var passageGroup = Raw(question, "group", "Group") as Dictionary<string, object>;
            var passageTitle = passageGroup != null ? Value(passageGroup, "title", "Title") : "";
            var passageText = passageGroup != null ? Value(passageGroup, "passage_text", "PassageText") : "";
            var passageImage = LocalizeDataImage(passageGroup != null ? Value(passageGroup, "image", "Image") : "");
            var questionText = Value(question, "text", "Text");
            var questionImage = LocalizeDataImage(Value(question, "image", "Image"));

            // A short one-line question and a full comprehension passage need very
            // different amounts of space. webViewInitialHeight is just a placeholder for
            // the instant before the embedded browser finishes laying out real content
            // (DocumentCompleted below) - it must NOT also be used as a floor on the real
            // measured height, or every question reserves this much room regardless of how
            // short it actually is (that was the cause of the large gap before questions).
            const int webViewInitialHeight = 90;
            const int minQuestionAreaHeight = 40;
            _questionWebView = new WebBrowser
            {
                Left = 32,
                Top = 58,
                Width = innerWidth,
                Height = webViewInitialHeight,
                ScrollBarsEnabled = false,
                AllowNavigation = false,
                WebBrowserShortcutsEnabled = false,
                IsWebBrowserContextMenuEnabled = false,
                BackColor = Color.White
            };
            body.Controls.Add(_questionWebView);

            var type = Value(question, "type", "Type").ToLowerInvariant();
            var options = JsonUtil.List(Raw(question, "options", "Options")).Select(JsonUtil.Text).Where(x => x.Length > 0).ToList();
            var isFreeText = type == "essay" || type == "theory" || type == "fill_blank" || type == "fill_in_the_blank" || !options.Any();
            var answerAreaHeight = isFreeText ? 230 : Math.Max(60, options.Count * 56 + 20);

            var answerContainer = new Panel { Left = 0, Top = 58 + webViewInitialHeight + 16, Width = main.Width, Height = answerAreaHeight, BackColor = Color.White };
            body.Controls.Add(answerContainer);

            if (isFreeText)
            {
                var answer = new TextBox
                {
                    Left = 32,
                    Top = 0,
                    Width = innerWidth,
                    Height = 190,
                    Multiline = true,
                    ScrollBars = ScrollBars.Vertical,
                    Tag = "answer",
                    Font = ReadableExamFont(12, false),
                    ForeColor = Palette.Text,
                    BackColor = Color.White
                };
                object saved;
                if (_answers.TryGetValue(QuestionId(question, _current), out saved)) answer.Text = JsonUtil.Text(saved);
                answerContainer.Controls.Add(answer);
            }
            else
            {
                for (var i = 0; i < options.Count; i++)
                {
                    var option = new RadioButton
                    {
                        Left = 38,
                        Top = i * 56,
                        Width = innerWidth - 8,
                        Height = 54,
                        Text = ((char)('A' + i)) + ". " + options[i],
                        Tag = "answer:" + i,
                        Font = ReadableExamFont(12, false),
                        ForeColor = Palette.Text,
                        BackColor = Color.White,
                        UseCompatibleTextRendering = true,
                        Enabled = true
                    };
                    object saved;
                    option.Checked = _answers.TryGetValue(QuestionId(question, _current), out saved) && JsonUtil.Text(saved) == i.ToString();
                    option.CheckedChanged += (s, e) => SaveCurrentAnswer(main);
                    answerContainer.Controls.Add(option);
                }
            }

            _questionWebView.DocumentCompleted += (s, e) =>
            {
                try
                {
                    if (_questionWebView.Document?.Body != null)
                    {
                        var loadedHeight = Math.Max(minQuestionAreaHeight, _questionWebView.Document.Body.ScrollRectangle.Height + 24);
                        _questionWebView.Height = loadedHeight;
                        answerContainer.Top = 58 + loadedHeight + 16;
                    }
                }
                catch { }
            };
            _questionWebView.DocumentText = BuildQuestionHtml(passageTitle, passageText, passageImage, questionText, questionImage);

            var prev = SecondaryButton("Previous", 32, 18, 120);
            prev.Enabled = _current > 0;
            prev.Click += (s, e) => { SaveCurrentAnswer(main); _current--; ShowExam(); };
            footer.Controls.Add(prev);
            var next = PrimaryButton(_current == _questions.Count - 1 ? "Review" : "Next", main.Width - 164, 18, 120);
            next.Click += (s, e) => { SaveCurrentAnswer(main); if (_current < _questions.Count - 1) _current++; ShowExam(); };
            footer.Controls.Add(next);
        }

        private static string BuildQuestionHtml(string passageTitle, string passageText, string passageImage, string questionText, string questionImage)
        {
            var sb = new StringBuilder();
            sb.Append("<!DOCTYPE html><html><head><meta charset='utf-8'><style>");
            sb.Append("body{font-family:'Segoe UI',Arial,sans-serif;font-size:13px;color:#162233;margin:4px 0;padding:0;line-height:1.6;}");
            sb.Append("p{margin:0 0 8px 0;}ul,ol{margin:0 0 8px 0;padding-left:20px;}");
            sb.Append("table{border-collapse:collapse;width:100%;margin:0 0 8px 0;}td,th{border:1px solid #ccd;padding:4px 8px;}");
            sb.Append(".passage{background:#f0f4fb;border-left:3px solid #1860b4;padding:10px 14px;margin:0 0 14px 0;}");
            sb.Append(".ptitle{font-weight:bold;color:#1860b4;margin:0 0 6px 0;font-size:12px;}");
            sb.Append("img{max-width:100%;height:auto;}");
            sb.Append("</style></head><body>");
            if (!string.IsNullOrWhiteSpace(passageText) || !string.IsNullOrWhiteSpace(passageImage))
            {
                sb.Append("<div class='passage'>");
                if (!string.IsNullOrWhiteSpace(passageTitle))
                    sb.Append("<p class='ptitle'>").Append(HtmlSafeText(passageTitle)).Append("</p>");
                if (!string.IsNullOrWhiteSpace(passageText))
                    sb.Append(LooksLikeHtml(passageText) ? passageText : "<p>" + HtmlSafeText(passageText).Replace("\n", "<br>") + "</p>");
                AppendImageTag(sb, passageImage);
                sb.Append("</div>");
            }
            if (!string.IsNullOrWhiteSpace(questionText))
                sb.Append(LooksLikeHtml(questionText) ? questionText : "<p>" + HtmlSafeText(questionText).Replace("\n", "<br>") + "</p>");
            AppendImageTag(sb, questionImage);
            sb.Append("</body></html>");
            return sb.ToString();
        }

        private static void AppendImageTag(StringBuilder sb, string imageSrc)
        {
            if (string.IsNullOrWhiteSpace(imageSrc)) return;
            sb.Append("<p><img src=\"").Append(HtmlSafeText(imageSrc).Replace("\"", "&quot;")).Append("\"></p>");
        }

        private static bool LooksLikeHtml(string text)
        {
            if (string.IsNullOrWhiteSpace(text)) return false;
            return text.IndexOf('<') >= 0 && (
                text.IndexOf("</", StringComparison.Ordinal) >= 0 ||
                text.IndexOf("/>", StringComparison.Ordinal) >= 0 ||
                text.IndexOf("<br", StringComparison.OrdinalIgnoreCase) >= 0 ||
                text.IndexOf("<p", StringComparison.OrdinalIgnoreCase) >= 0 ||
                text.IndexOf("<div", StringComparison.OrdinalIgnoreCase) >= 0
            );
        }

        private static string HtmlSafeText(string text)
        {
            return (text ?? "").Replace("&", "&amp;").Replace("<", "&lt;").Replace(">", "&gt;");
        }

        // The Instructions screen shows this in a plain TextBox, not the WebBrowser used for
        // question text - a TextBox has no HTML renderer at all, so tags like <br> from the
        // exam builder's rich-text editor would otherwise show up as literal text.
        private static string HtmlToPlainText(string value)
        {
            var text = value ?? "";
            if (text.IndexOf('<') < 0) return text;
            var looksLikeHtml = Regex.IsMatch(text, @"</[a-z]+>|<br\s*/?>|<p[\s>]|<div[\s>]|<li[\s>]", RegexOptions.IgnoreCase);
            if (!looksLikeHtml) return text;

            var result = Regex.Replace(text, @"<\s*br\s*/?>", "\n", RegexOptions.IgnoreCase);
            result = Regex.Replace(result, @"</\s*(p|div|li|h[1-6]|tr)\s*>", "\n", RegexOptions.IgnoreCase);
            result = Regex.Replace(result, @"<\s*li[^>]*>", "- ", RegexOptions.IgnoreCase);
            result = Regex.Replace(result, @"<[^>]+>", "");
            result = result
                .Replace("&nbsp;", " ")
                .Replace("&lt;", "<")
                .Replace("&gt;", ">")
                .Replace("&quot;", "\"")
                .Replace("&#39;", "'")
                .Replace("&apos;", "'")
                .Replace("&amp;", "&");
            result = Regex.Replace(result, @"[ \t]+\n", "\n");
            result = Regex.Replace(result, @"\n{3,}", "\n\n");
            return result.Trim();
        }

        private void SaveCurrentAnswer(Control container)
        {
            if (!_examMode || _questions.Count == 0 || container == null) return;
            var qid = QuestionId(_questions[_current], _current);
            foreach (Control control in AllControls(container))
            {
                if (control.Tag == null) continue;
                var tag = JsonUtil.Text(control.Tag);
                if (tag == "answer" && control is TextBox)
                {
                    var value = ((TextBox)control).Text;
                    if (string.IsNullOrWhiteSpace(value)) _answers.Remove(qid); else _answers[qid] = value;
                }
                if (tag.StartsWith("answer:") && control is RadioButton && ((RadioButton)control).Checked)
                {
                    _answers[qid] = tag.Substring("answer:".Length);
                }
            }
        }

        private void SubmitExam()
        {
            if (_submitting) return;
            SaveCurrentAnswer(_questionPanel);
            _dialogOpen = true;
            var confirm = MessageBox.Show(this, "Submit your exam now?", "Submit", MessageBoxButtons.YesNo, MessageBoxIcon.Question);
            _dialogOpen = false;
            if (confirm != DialogResult.Yes) return;
            _submitting = true;
            try
            {
                var submitted = _client.Submit(Value(_session, "id", "Id"), _answers);
                if (!Convert.ToBoolean(submitted.ContainsKey("success") ? submitted["success"] : false))
                {
                    throw new InvalidOperationException(JsonUtil.Text(submitted.ContainsKey("message") ? submitted["message"] : "The LAN server rejected the submission."));
                }
                FinishSubmitted("Exam submitted successfully.", "Submitted");
            }
            catch (Exception ex)
            {
                _submitting = false;
                _dialogOpen = true;
                MessageBox.Show(this, ex.Message, "Submit failed");
                _dialogOpen = false;
            }
        }

        private void TimerTick(object sender, EventArgs e)
        {
            if (!_examMode || _session == null) return;
            TopMost = true;
            if (FormBorderStyle != FormBorderStyle.None) FormBorderStyle = FormBorderStyle.None;
            if (WindowState != FormWindowState.Maximized) WindowState = FormWindowState.Maximized;
            SaveCurrentAnswer(_questionPanel);
            var now = DateTime.UtcNow;
            if (_lastSaveSecond != now.Second)
            {
                _lastSaveSecond = now.Second;
                SaveAnswersLocally();
                try
                {
                    var saved = _client.SaveAnswers(Value(_session, "id", "Id"), _answers);
                    if (saved.ContainsKey("session")) _session = saved["session"] as Dictionary<string, object> ?? _session;
                    SyncServerTimer(saved);
                    MarkLanConnected();
                }
                catch
                {
                    MarkLanDisconnected(now);
                }
            }
            if (_timeLabel != null) _timeLabel.Text = TimeText();
            if (CurrentRemainingSeconds() == 0)
            {
                AutoSubmit("Time is up. Your exam has been submitted.", "Time up");
                return;
            }
            if (_offlineSince.HasValue && (now - _offlineSince.Value).TotalSeconds >= 15)
            {
                _pendingAutoSubmit = true;
                UpdateLanLabel("LAN: Disconnected - submitting when available", Palette.Coral);
                try
                {
                    var submitted = _client.Submit(Value(_session, "id", "Id"), _answers);
                    if (Convert.ToBoolean(submitted.ContainsKey("success") ? submitted["success"] : false))
                    {
                        FinishSubmitted("LAN was lost for 15 seconds. The exam has been submitted.", "Connection lost");
                    }
                }
                catch
                {
                    UpdateLanLabel("LAN: Waiting to reconnect", Palette.Coral);
                }
            }
        }

        private void AutoSubmit(string message, string title)
        {
            try
            {
                var submitted = _client.Submit(Value(_session, "id", "Id"), _answers);
                if (Convert.ToBoolean(submitted.ContainsKey("success") ? submitted["success"] : false))
                {
                    FinishSubmitted(message, title);
                    return;
                }
            }
            catch
            {
                MarkLanDisconnected(DateTime.UtcNow);
                _pendingAutoSubmit = true;
                UpdateLanLabel("LAN: Time up - submitting when available", Palette.Coral);
            }
        }

        private void FinishSubmitted(string message, string title)
        {
            _timer.Stop();
            _examMode = false;
            _pendingAutoSubmit = false;
            _offlineSince = null;
            TopMost = false;
            _dialogOpen = true;
            MessageBox.Show(this, message, title);
            _dialogOpen = false;
            ShowConnect();
        }

        private void MarkLanConnected()
        {
            if (_offlineSince.HasValue && !_pendingAutoSubmit) UpdateLanLabel("LAN: Reconnected", Palette.GreenSoft);
            else if (!_pendingAutoSubmit) UpdateLanLabel("LAN: Connected", Palette.GreenSoft);
            else UpdateLanLabel("LAN: Reconnected - exam resumed", Palette.GreenSoft);
            _pendingAutoSubmit = false;
            _offlineSince = null;
        }

        private void MarkLanDisconnected(DateTime now)
        {
            if (!_offlineSince.HasValue) _offlineSince = now;
            var elapsed = Math.Min(15, (int)(now - _offlineSince.Value).TotalSeconds);
            UpdateLanLabel("LAN: Offline " + elapsed + "s", Palette.Coral);
        }

        private void UpdateLanLabel(string text, Color color)
        {
            if (_lanLabel == null) return;
            _lanLabel.Text = text;
            _lanLabel.ForeColor = color;
            _lanLabel.Refresh();
        }

        private void MainFormDeactivate(object sender, EventArgs e)
        {
            if (!_examMode || _session == null) return;
            if (_calculatorOpen || _dialogOpen) return;
            try { _client.FocusLoss(Value(_session, "id", "Id")); } catch { }
            BeginInvoke(new Action(() =>
            {
                TopMost = true;
                WindowState = FormWindowState.Maximized;
                Activate();
            }));
        }

        private void MainFormKeyDown(object sender, KeyEventArgs e)
        {
            if (!_examMode) return;
            if (e.Alt || e.KeyCode == Keys.Escape || e.KeyCode == Keys.LWin || e.KeyCode == Keys.RWin)
            {
                e.Handled = true;
                e.SuppressKeyPress = true;
                try { _client.FocusLoss(Value(_session, "id", "Id")); } catch { }
            }
        }

        private void MainFormClosing(object sender, FormClosingEventArgs e)
        {
            if (!_examMode) return;
            e.Cancel = true;
            _dialogOpen = true;
            MessageBox.Show(this, "Exam is still running. Submit the exam before closing this app.", "Exam running", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            _dialogOpen = false;
        }

        private void ShowCalculator()
        {
            _calculatorOpen = true;
            var form = new Form
            {
                Text = "Calculator",
                Width = 360,
                Height = 430,
                StartPosition = FormStartPosition.CenterParent,
                TopMost = true,
                FormBorderStyle = FormBorderStyle.FixedDialog,
                MaximizeBox = false,
                MinimizeBox = false,
                BackColor = Palette.Background,
                Font = new Font("Segoe UI", 10),
                KeyPreview = true
            };
            form.FormClosed += (s, e) =>
            {
                _calculatorOpen = false;
                if (_examMode)
                {
                    TopMost = true;
                    WindowState = FormWindowState.Maximized;
                    Activate();
                }
            };
            var input = new TextBox
            {
                Left = 16,
                Top = 16,
                Width = 310,
                Height = 34,
                Font = new Font("Segoe UI", 13),
                TextAlign = HorizontalAlignment.Right
            };
            var result = Label("", 16, 58, 12, true, 310, Palette.Blue);
            form.Controls.Add(input);
            form.Controls.Add(result);

            string[,] keys =
            {
                { "7", "8", "9", "/" },
                { "4", "5", "6", "*" },
                { "1", "2", "3", "-" },
                { "0", ".", "(", ")" },
                { "C", "Del", "+", "=" }
            };
            for (var row = 0; row < 5; row++)
            {
                for (var col = 0; col < 4; col++)
                {
                    var key = keys[row, col];
                    var displayKey = key == "/" ? "÷" : key == "*" ? "×" : key;
                    var button = key == "=" ? PrimaryButton(displayKey, 16 + col * 78, 96 + row * 54, 70) : SecondaryButton(displayKey, 16 + col * 78, 96 + row * 54, 70);
                    button.Tag = key;
                    button.Height = 44;
                    button.Font = new Font("Segoe UI", 12, FontStyle.Bold);
                    button.Click += (s, e) =>
                    {
                        var value = JsonUtil.Text(((Button)s).Tag);
                        if (value == "C")
                        {
                            input.Text = "";
                            result.Text = "";
                        }
                        else if (value == "Del")
                        {
                            if (input.Text.Length > 0) input.Text = input.Text.Substring(0, input.Text.Length - 1);
                        }
                        else if (value == "=")
                        {
                            try
                            {
                                var answer = Convert.ToString(new System.Data.DataTable().Compute(NormalizeExpression(input.Text), ""));
                                result.Text = "= " + answer;
                                input.Text = answer;
                                input.SelectionStart = input.Text.Length;
                            }
                            catch { result.Text = "Invalid expression"; }
                        }
                        else
                        {
                            input.Text += value;
                            input.SelectionStart = input.Text.Length;
                        }
                    };
                    form.Controls.Add(button);
                }
            }
            form.Shown += (s, e) =>
            {
                form.Activate();
                input.Focus();
            };
            form.ShowDialog(this);
        }

        private string NormalizeExpression(string expression)
        {
            return (expression ?? "")
                .Replace("×", "*")
                .Replace("÷", "/")
                .Replace("−", "-");
        }

        /// <summary>
        /// Seeds the server-anchored countdown from any LAN response that included
        /// time_remaining_seconds (start-session, begin-exam, and every per-second
        /// save-answers poll). Call this every time a response is read, regardless of
        /// which endpoint produced it.
        /// </summary>
        private void SyncServerTimer(Dictionary<string, object> response)
        {
            if (response == null || !response.ContainsKey("time_remaining_seconds")) return;
            _serverRemainingSeconds = JsonUtil.Int(response["time_remaining_seconds"], 0);
            _serverSyncTickCount = Environment.TickCount;
        }

        /// <summary>
        /// Seconds left, ticked forward locally (via the monotonic Environment.TickCount)
        /// since the last time the admin LAN server told us the real remaining time. Falls
        /// back to a purely local countdown from the exam's configured duration (also
        /// anchored to Environment.TickCount, never a wall clock) if this device has never
        /// received a server-timed response yet (e.g. an old admin build) - see the field
        /// comments on _localExamStartTick/_localExamDurationSeconds for why.
        /// </summary>
        private int CurrentRemainingSeconds()
        {
            if (_serverRemainingSeconds.HasValue)
            {
                var elapsedSeconds = unchecked(Environment.TickCount - _serverSyncTickCount) / 1000;
                return Math.Max(0, _serverRemainingSeconds.Value - Math.Max(0, elapsedSeconds));
            }
            if (_localExamDurationSeconds > 0)
            {
                var elapsedSeconds = unchecked(Environment.TickCount - _localExamStartTick) / 1000;
                return Math.Max(0, _localExamDurationSeconds - Math.Max(0, elapsedSeconds));
            }
            return -1;
        }

        private string TimeText()
        {
            if (_session == null) return "";
            var remaining = CurrentRemainingSeconds();
            if (remaining < 0) return "";
            var span = TimeSpan.FromSeconds(remaining);
            return "Time: " + ((int)span.TotalHours).ToString("00") + ":" + span.Minutes.ToString("00") + ":" + span.Seconds.ToString("00");
        }

        private Control CreateStudentBadge(int left, int top, bool dark)
        {
            var panel = new Panel { Left = left, Top = top, Width = 250, Height = 58, BackColor = dark ? Palette.Navy : Color.White };
            panel.Controls.Add(CreateProfileControl(0, 4, 48));
            var name = Label(DisplayStudentName(), 58, 2, 10, true, 188, dark ? Color.White : Palette.Text);
            var id = Label(DisplayStudentId(), 58, 28, 9, false, 188, dark ? Palette.SoftText : Palette.Muted);
            panel.Controls.Add(name);
            panel.Controls.Add(id);
            return panel;
        }

        private Control CreateLargeStudentBadge(int left, int top)
        {
            var panel = new Panel { Left = left, Top = top, Width = 242, Height = 136, BackColor = Color.White };
            panel.Controls.Add(CreateProfileControl(0, 0, 88));
            panel.Controls.Add(Label(DisplayStudentName(), 102, 6, 12, true, 132, Palette.Text));
            panel.Controls.Add(Label(DisplayStudentId(), 102, 54, 10, true, 132, Palette.Blue));
            var className = Value(_student, "class_name", "ClassName", "class_label", "ClassLabel");
            if (!string.IsNullOrWhiteSpace(className))
            {
                panel.Controls.Add(Label(className, 0, 102, 9, false, 232, Palette.Muted));
            }
            return panel;
        }

        private Control CreateProfileControl(int left, int top, int size)
        {
            var photoData = Value(_student, "profile_picture_data", "ProfilePictureData", "photo_data", "PhotoData");
            if (photoData.StartsWith("data:image/", StringComparison.OrdinalIgnoreCase))
            {
                var dataBox = new PictureBox
                {
                    Left = left,
                    Top = top,
                    Width = size,
                    Height = size,
                    BackColor = Palette.LightButton,
                    SizeMode = PictureBoxSizeMode.Zoom
                };
                MakeCircle(dataBox);
                try { dataBox.Image = ImageFromDataUrl(photoData); return dataBox; } catch { }
            }
            var photoUrl = Value(_student, "profile_picture", "ProfilePicture", "profile_picture_url", "PhotoUrl");
            if (photoUrl.StartsWith("http://", StringComparison.OrdinalIgnoreCase) || photoUrl.StartsWith("https://", StringComparison.OrdinalIgnoreCase))
            {
                var box = new PictureBox
                {
                    Left = left,
                    Top = top,
                    Width = size,
                    Height = size,
                    BackColor = Palette.LightButton,
                    SizeMode = PictureBoxSizeMode.Zoom
                };
                MakeCircle(box);
                try { box.LoadAsync(photoUrl); return box; } catch { }
            }
            var badge = new Label
            {
                Text = Initials(DisplayStudentName()),
                Left = left,
                Top = top,
                Width = size,
                Height = size,
                BackColor = Palette.Blue,
                ForeColor = Color.White,
                TextAlign = ContentAlignment.MiddleCenter,
                Font = new Font("Segoe UI", 12, FontStyle.Bold)
            };
            MakeCircle(badge);
            return badge;
        }

        private Image ImageFromDataUrl(string dataUrl)
        {
            var comma = (dataUrl ?? "").IndexOf(',');
            if (comma < 0) throw new InvalidOperationException("Invalid image data.");
            var bytes = Convert.FromBase64String(dataUrl.Substring(comma + 1));
            using (var stream = new MemoryStream(bytes))
            {
                return Image.FromStream(stream);
            }
        }

        private void MakeCircle(Control control)
        {
            var path = new GraphicsPath();
            path.AddEllipse(0, 0, control.Width - 1, control.Height - 1);
            control.Region = new Region(path);
        }

        private string DisplayStudentName()
        {
            var name = Value(_student, "full_name", "FullName", "name", "Name", "email", "Email");
            if (!string.IsNullOrWhiteSpace(name)) return name;
            var first = Value(_student, "first_name", "FirstName");
            var last = Value(_student, "last_name", "LastName");
            name = (first + " " + last).Trim();
            return string.IsNullOrWhiteSpace(name) ? DisplayStudentId() : name;
        }

        private string DisplayStudentId()
        {
            var id = Value(_student, "student_id", "StudentId", "admission_number", "AdmissionNumber", "id", "Id");
            return string.IsNullOrWhiteSpace(id) ? _studentId : id;
        }

        private IEnumerable<Control> AllControls(Control parent)
        {
            foreach (Control control in parent.Controls)
            {
                yield return control;
                foreach (var nested in AllControls(control)) yield return nested;
            }
        }

        private static string Value(Dictionary<string, object> item, params string[] keys)
        {
            if (item == null) return "";
            foreach (var key in keys)
            {
                if (item.ContainsKey(key)) return JsonUtil.Text(item[key]);
            }
            return "";
        }

        private static object Raw(Dictionary<string, object> item, params string[] keys)
        {
            if (item == null) return null;
            foreach (var key in keys)
            {
                if (item.ContainsKey(key)) return item[key];
            }
            return null;
        }

        private string QuestionId(Dictionary<string, object> q, int index)
        {
            var id = Value(q, "id", "Id");
            return string.IsNullOrWhiteSpace(id) ? "question_" + index : id;
        }
        private static string Initials(string name)
        {
            var parts = (name ?? "").Split(new[] { ' ' }, StringSplitOptions.RemoveEmptyEntries);
            if (parts.Length == 0) return "SD";
            if (parts.Length == 1) return parts[0].Substring(0, Math.Min(2, parts[0].Length)).ToUpperInvariant();
            return (parts[0].Substring(0, 1) + parts[1].Substring(0, 1)).ToUpperInvariant();
        }
        private void SetStatus(string text, Color color) { if (_status != null) { _status.Text = text; _status.ForeColor = color; _status.Refresh(); } }
        private Panel Card(int left, int top, int width, int height) { return new Panel { Left = left, Top = top, Width = width, Height = height, BackColor = Color.White, BorderStyle = BorderStyle.FixedSingle }; }
        private TextBox Field(Control parent, string label, string value, int left, int top, bool password) { parent.Controls.Add(Label(label, left, top - 30, 9, true, 220, Palette.Text)); var box = new TextBox { Left = left, Top = top, Width = 226, Height = 34, Text = value, UseSystemPasswordChar = password, Font = new Font("Segoe UI", 11) }; parent.Controls.Add(box); return box; }
        private void ApplyNumbersOnly(TextBox box)
        {
            box.KeyPress += (sender, args) =>
            {
                if (!char.IsControl(args.KeyChar) && !char.IsDigit(args.KeyChar)) args.Handled = true;
            };
            box.TextChanged += (sender, args) =>
            {
                var clean = "";
                foreach (char c in box.Text)
                {
                    if (char.IsDigit(c)) clean += c;
                }
                if (clean == box.Text) return;
                var selectionStart = box.SelectionStart;
                box.Text = clean;
                box.SelectionStart = selectionStart > box.Text.Length ? box.Text.Length : selectionStart;
            };
        }
        private Label Label(string text, int left, int top, int size, bool bold, int width, Color color) { return new Label { Text = text, Left = left, Top = top, AutoSize = true, MaximumSize = new Size(width, 0), Font = new Font("Segoe UI", size, bold ? FontStyle.Bold : FontStyle.Regular), ForeColor = color, UseCompatibleTextRendering = true }; }
        private Font MathFont(float size) { try { return new Font("Cambria Math", size, FontStyle.Regular); } catch { return new Font("Segoe UI Symbol", size, FontStyle.Regular); } }
        private Font ReadableExamFont(float size, bool bold) { return new Font("Segoe UI", size, bold ? FontStyle.Bold : FontStyle.Regular); }
        private Button PrimaryButton(string text, int left, int top, int width) { var b = new Button { Text = text, Left = left, Top = top, Width = width, Height = 42, BackColor = Palette.Blue, ForeColor = Color.White, FlatStyle = FlatStyle.Flat, Font = new Font("Segoe UI", 10, FontStyle.Bold) }; b.FlatAppearance.BorderColor = Palette.Blue; return b; }
        private Button SecondaryButton(string text, int left, int top, int width) { var b = PrimaryButton(text, left, top, width); b.BackColor = Palette.LightButton; b.ForeColor = Palette.Text; b.FlatAppearance.BorderColor = Palette.Border; return b; }
    }

    internal static class Palette
    {
        public static readonly Color Background = Color.FromArgb(244, 247, 251);
        public static readonly Color Navy = Color.FromArgb(15, 32, 55);
        public static readonly Color Text = Color.FromArgb(22, 34, 51);
        public static readonly Color Muted = Color.FromArgb(96, 112, 132);
        public static readonly Color SoftText = Color.FromArgb(196, 207, 221);
        public static readonly Color Border = Color.FromArgb(214, 223, 235);
        public static readonly Color LightButton = Color.FromArgb(235, 241, 248);
        public static readonly Color Blue = Color.FromArgb(24, 96, 180);
        public static readonly Color Green = Color.FromArgb(37, 137, 92);
        public static readonly Color GreenSoft = Color.FromArgb(198, 232, 215);
        public static readonly Color Coral = Color.FromArgb(196, 74, 62);
    }
}