using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.IO;
using System.Linq;
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

        public MainForm()
        {
            Text = "SchoolDom Student CBT v" + Application.ProductVersion;
            Width = 1120;
            Height = 740;
            MinimumSize = new Size(960, 620);
            StartPosition = FormStartPosition.CenterScreen;
            BackColor = Palette.Background;
            Font = new Font("Segoe UI", 10);
            AutoScaleMode = AutoScaleMode.Font;
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

            var start = PrimaryButton("Start Exam", 180, 374, 150);
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
                    var choices = JsonUtil.List(login.ContainsKey("exams") ? login["exams"] : null)
                        .Select(item => item as Dictionary<string, object>)
                        .Where(item => item != null)
                        .ToList();
                    if (choices.Count > 1)
                    {
                        ShowExamSelection(choices);
                        return;
                    }
                    _exam = login.ContainsKey("exam") ? login["exam"] as Dictionary<string, object> : choices.FirstOrDefault();
                    _session = login.ContainsKey("session") ? login["session"] as Dictionary<string, object> : null;
                    if (_exam == null)
                    {
                        MessageBox.Show("No exam was returned for this Student ID and PIN.", "No exam");
                        return;
                    }
                    if (_session == null) StartSelectedExam(_exam);
                    else ShowInstructions();
                }
                catch (Exception ex)
                {
                    SetStatus("Could not start exam.", Palette.Coral);
                    MessageBox.Show(ex.Message, "Start failed");
                }
            };
            card.Controls.Add(start);

            _root.Controls.Add(content);
            _root.Controls.Add(hero);
        }

        private void ShowExamSelection(List<Dictionary<string, object>> exams)
        {
            _examMode = false;
            _timer.Stop();
            _root.Controls.Clear();

            var header = new Panel { Dock = DockStyle.Top, Height = 84, BackColor = Palette.Navy };
            header.Controls.Add(Label("Select Exam", 28, 18, 18, true, 420, Color.White));
            header.Controls.Add(Label(Value(_student, "full_name", "FullName") + "  " + Value(_student, "student_id", "StudentId"), 30, 50, 10, false, 560, Palette.SoftText));
            _root.Controls.Add(header);

            var content = new Panel { Dock = DockStyle.Fill, BackColor = Palette.Background, AutoScroll = true };
            var y = 30;
            foreach (var exam in exams)
            {
                var card = Card(42, y, 760, 112);
                card.Controls.Add(Label(Value(exam, "title", "Title"), 22, 18, 14, true, 520, Palette.Text));
                card.Controls.Add(Label(Value(exam, "subject", "Subject") + "  " + Math.Max(1, JsonUtil.Int(Raw(exam, "duration_seconds", "DurationSeconds"), 3600) / 60) + " minute(s)", 22, 54, 10, false, 520, Palette.Muted));
                var start = PrimaryButton("Select", 620, 34, 110);
                var selected = exam;
                start.Click += (s, e) => StartSelectedExam(selected);
                card.Controls.Add(start);
                content.Controls.Add(card);
                y += 130;
            }
            _root.Controls.Add(content);
        }

        private void StartSelectedExam(Dictionary<string, object> exam)
        {
            var started = _client.StartSession(_studentId, Value(exam, "id", "Id"));
            if (!Convert.ToBoolean(started.ContainsKey("success") ? started["success"] : false))
            {
                MessageBox.Show(JsonUtil.Text(started.ContainsKey("message") ? started["message"] : "Could not start exam."), "Start failed");
                ShowConnect();
                return;
            }
            _exam = started["exam"] as Dictionary<string, object>;
            _session = started["session"] as Dictionary<string, object>;
            ShowInstructions();
        }

        private void ShowInstructions()
        {
            LoadExamDetail();
            _root.Controls.Clear();
            var header = new Panel { Dock = DockStyle.Top, Height = 84, BackColor = Palette.Navy };
            header.Controls.Add(Label(Value(_exam, "title", "Title"), 28, 18, 18, true, 620, Color.White));
            header.Controls.Add(Label("Read the instructions before starting.", 30, 52, 10, false, 520, Palette.SoftText));

            var content = new Panel { Dock = DockStyle.Fill, BackColor = Palette.Background };
            var card = Card(0, 0, 780, 440);
            Action centerCard = () =>
            {
                card.Left = Math.Max(24, (content.ClientSize.Width - card.Width) / 2);
                card.Top = 54;
            };
            content.Resize += (s, e) => centerCard();
            centerCard();
            card.Controls.Add(Label("Instructions", 28, 24, 16, true, 680, Palette.Text));
            var instructions = new TextBox
            {
                Left = 30,
                Top = 72,
                Width = 720,
                Height = 260,
                Multiline = true,
                ReadOnly = true,
                ScrollBars = ScrollBars.Vertical,
                Text = string.IsNullOrWhiteSpace(Value(_exam, "instructions", "Instructions")) ? "No special instructions." : Value(_exam, "instructions", "Instructions"),
                Font = new Font("Segoe UI", 11),
                BorderStyle = BorderStyle.FixedSingle
            };
            card.Controls.Add(instructions);
            card.Controls.Add(Label(_questions.Count + " question(s)  " + Math.Max(1, JsonUtil.Int(Raw(_exam, "duration_seconds", "DurationSeconds"), 3600) / 60) + " minute(s)", 30, 350, 10, true, 520, Palette.Muted));
            var start = PrimaryButton("Start Exam", 30, 386, 150);
            start.Click += (s, e) => EnterExamMode();
            card.Controls.Add(start);
            content.Controls.Add(card);
            _root.Controls.Add(content);
            _root.Controls.Add(header);
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
            var cardHeight = Math.Max(520, availableHeight - 64);
            var totalWidth = sideWidth + gap + mainWidth;
            var left = Math.Max(24, (availableWidth - totalWidth) / 2);
            var top = 24;
            var side = Card(left, top, sideWidth, cardHeight);
            var main = Card(left + sideWidth + gap, top, mainWidth, cardHeight);
            content.Controls.Add(side);
            content.Controls.Add(main);
            _root.Controls.Add(content);

            side.Controls.Add(CreateLargeStudentBadge(18, 42));
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

            var innerWidth = main.Width - 84;
            body.Controls.Add(Label("Question " + (_current + 1) + " of " + _questions.Count, 32, 24, 10, true, 260, Palette.Muted));
            
            // ** FIX: Use WebBrowser to render HTML content instead of Label **
            _questionWebView = new WebBrowser
            {
                Left = 32,
                Top = 70,
                Width = innerWidth,
                Height = 300,
                DocumentText = Value(question, "text", "Text"),
                ScrollBarsEnabled = true,
                AllowNavigation = false,
                WebBrowserShortcutsEnabled = false,
                IsWebBrowserContextMenuEnabled = false,
                BackColor = Color.White,
                BorderStyle = BorderStyle.None
            };
            // Wait for document to load before reading height
            _questionWebView.DocumentCompleted += (s, e) =>
            {
                try
                {
                    var doc = _questionWebView.Document;
                    if (doc != null)
                    {
                        var element = doc.Body;
                        if (element != null)
                        {
                            _questionWebView.Height = Math.Max(150, element.ScrollRectangle.Height + 20);
                        }
                    }
                }
                catch { }
            };
            body.Controls.Add(_questionWebView);

            var top = Math.Max(160, 70 + _questionWebView.Height + 20);
            var type = Value(question, "type", "Type").ToLowerInvariant();
            var options = JsonUtil.List(Raw(question, "options", "Options")).Select(JsonUtil.Text).Where(x => x.Length > 0).ToList();

            if (type == "essay" || type == "theory" || type == "fill_blank" || type == "fill_in_the_blank" || !options.Any())
            {
                var answer = new TextBox
                {
                    Left = 32,
                    Top = top,
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
                body.Controls.Add(answer);
            }
            else
            {
                for (var i = 0; i < options.Count; i++)
                {
                    var optionTop = top + i * 56;
                    var option = new RadioButton
                    {
                        Left = 38,
                        Top = optionTop,
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
                    body.Controls.Add(option);
                }
            }

            var prev = SecondaryButton("Previous", 32, 18, 120);
            prev.Enabled = _current > 0;
            prev.Click += (s, e) => { SaveCurrentAnswer(main); _current--; ShowExam(); };
            footer.Controls.Add(prev);
            var next = PrimaryButton(_current == _questions.Count - 1 ? "Review" : "Next", main.Width - 164, 18, 120);
            next.Click += (s, e) => { SaveCurrentAnswer(main); if (_current < _questions.Count - 1) _current++; ShowExam(); };
            footer.Controls.Add(next);
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
                    MarkLanConnected();
                }
                catch
                {
                    MarkLanDisconnected(now);
                }
            }
            if (_timeLabel != null) _timeLabel.Text = TimeText();
            DateTime ends;
            if (DateTime.TryParse(Value(_session, "ends_at", "EndsAt"), out ends) && DateTime.UtcNow >= ends.ToUniversalTime())
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

        private string TimeText()
        {
            DateTime ends;
            if (_session == null || !DateTime.TryParse(Value(_session, "ends_at", "EndsAt"), out ends)) return "";
            var span = ends.ToUniversalTime() - DateTime.UtcNow;
            if (span.TotalSeconds < 0) span = TimeSpan.Zero;
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