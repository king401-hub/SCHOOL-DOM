using System;
using System.Collections.Generic;
using System.Drawing;
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

        public MainForm()
        {
            Text = "SchoolDom Student CBT";
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
            var card = Card(80, 90, 560, 410);
            content.Controls.Add(card);
            card.Controls.Add(Label("Exam Login", 34, 30, 20, true, 420, Palette.Text));
            card.Controls.Add(Label("The app connects to the admin LAN server automatically. No internet login is needed.", 36, 76, 10, false, 480, Palette.Muted));

            var server = Field(card, "LAN Server", "", 36, 150, false);
            server.Width = 500;
            var studentId = Field(card, "Student ID", "", 36, 230, false);
            var pin = Field(card, "Exam PIN", "", 306, 230, true);
            _status = Label("", 36, 346, 10, false, 490, Palette.Muted);
            card.Controls.Add(_status);

            var discover = SecondaryButton("Find LAN", 36, 292, 130);
            discover.Click += (s, e) =>
            {
                try
                {
                    SetStatus("Searching for admin LAN server...", Palette.Muted);
                    server.Text = _client.Discover();
                    SetStatus("Connected to " + server.Text, Palette.Green);
                }
                catch (Exception ex)
                {
                    SetStatus("Could not find LAN server. Ask admin to start LAN.", Palette.Coral);
                    MessageBox.Show(ex.Message, "LAN discovery failed");
                }
            };
            card.Controls.Add(discover);

            var start = PrimaryButton("Start Exam", 180, 292, 150);
            start.Click += (s, e) =>
            {
                try
                {
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
            _root.Controls.Add(header);

            var content = new Panel { Dock = DockStyle.Fill, BackColor = Palette.Background };
            var card = Card(60, 40, 780, 440);
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

        private void EnterExamMode()
        {
            _examMode = true;
            _current = 0;
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
            var header = new Panel { Dock = DockStyle.Top, Height = 70, BackColor = Palette.Navy };
            header.Controls.Add(Label(Value(_exam, "title", "Title"), 24, 16, 17, true, 620, Color.White));
            _timeLabel = Label(TimeText(), Width - 250, 22, 12, true, 210, Color.White);
            header.Controls.Add(_timeLabel);
            _root.Controls.Add(header);

            var content = new Panel { Dock = DockStyle.Fill, BackColor = Palette.Background };
            var side = Card(24, 24, 230, 580);
            var main = Card(278, 24, 760, 580);
            content.Controls.Add(side);
            content.Controls.Add(main);
            _root.Controls.Add(content);

            var initials = Initials(Value(_student, "full_name", "FullName"));
            var avatar = new Label { Text = initials, Left = 18, Top = 16, Width = 46, Height = 46, BackColor = Palette.Blue, ForeColor = Color.White, TextAlign = ContentAlignment.MiddleCenter, Font = new Font("Segoe UI", 12, FontStyle.Bold) };
            side.Controls.Add(avatar);
            side.Controls.Add(Label(Value(_student, "full_name", "FullName"), 74, 14, 10, true, 140, Palette.Text));
            side.Controls.Add(Label(Value(_student, "student_id", "StudentId"), 74, 44, 9, false, 140, Palette.Muted));
            side.Controls.Add(Label("Questions", 18, 92, 10, true, 190, Palette.Text));
            for (var i = 0; i < _questions.Count; i++)
            {
                var index = i;
                var button = new Button
                {
                    Text = (i + 1).ToString(),
                    Left = 18 + (i % 5) * 40,
                    Top = 126 + (i / 5) * 40,
                    Width = 32,
                    Height = 32,
                    FlatStyle = FlatStyle.Flat,
                    BackColor = _answers.ContainsKey(QuestionId(_questions[i], i)) ? Palette.GreenSoft : Palette.LightButton,
                    ForeColor = Palette.Text
                };
                if (i == _current) { button.BackColor = Palette.Blue; button.ForeColor = Color.White; }
                button.Click += (s, e) => { SaveCurrentAnswer(main); _current = index; ShowExam(); };
                side.Controls.Add(button);
            }

            var calc = SecondaryButton("Calculator", 18, 460, 190);
            calc.Click += (s, e) => ShowCalculator();
            side.Controls.Add(calc);
            var submit = PrimaryButton("Submit Exam", 18, 514, 190);
            submit.Click += (s, e) => SubmitExam();
            side.Controls.Add(submit);

            RenderQuestion(main);
        }

        private void RenderQuestion(Panel main)
        {
            _questionPanel = main;
            var question = _questions[_current];
            main.Controls.Add(Label("Question " + (_current + 1) + " of " + _questions.Count, 24, 20, 10, true, 260, Palette.Muted));
            var text = Label(Value(question, "text", "Text"), 24, 62, 13, true, 700, Palette.Text);
            main.Controls.Add(text);
            var top = Math.Max(160, text.Top + text.Height + 20);
            var type = Value(question, "type", "Type").ToLowerInvariant();
            var options = JsonUtil.List(Raw(question, "options", "Options")).Select(JsonUtil.Text).Where(x => x.Length > 0).ToList();

            if (type == "essay" || type == "theory" || type == "fill_blank" || type == "fill_in_the_blank" || !options.Any())
            {
                var answer = new TextBox { Left = 24, Top = top, Width = 700, Height = 190, Multiline = true, ScrollBars = ScrollBars.Vertical, Tag = "answer" };
                object saved;
                if (_answers.TryGetValue(QuestionId(question, _current), out saved)) answer.Text = JsonUtil.Text(saved);
                main.Controls.Add(answer);
            }
            else
            {
                for (var i = 0; i < options.Count; i++)
                {
                    var option = new RadioButton { Left = 30, Top = top + i * 46, Width = 680, Height = 36, Text = ((char)('A' + i)) + ". " + options[i], Tag = "answer:" + i, Font = new Font("Segoe UI", 11) };
                    object saved;
                    option.Checked = _answers.TryGetValue(QuestionId(question, _current), out saved) && JsonUtil.Text(saved) == i.ToString();
                    option.CheckedChanged += (s, e) => SaveCurrentAnswer(main);
                    main.Controls.Add(option);
                }
            }

            var prev = SecondaryButton("Previous", 24, 510, 120);
            prev.Enabled = _current > 0;
            prev.Click += (s, e) => { SaveCurrentAnswer(main); _current--; ShowExam(); };
            main.Controls.Add(prev);
            var next = PrimaryButton(_current == _questions.Count - 1 ? "Review" : "Next", 156, 510, 120);
            next.Click += (s, e) => { SaveCurrentAnswer(main); if (_current < _questions.Count - 1) _current++; ShowExam(); };
            main.Controls.Add(next);
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
            if (MessageBox.Show("Submit your exam now?", "Submit", MessageBoxButtons.YesNo, MessageBoxIcon.Question) != DialogResult.Yes) return;
            _submitting = true;
            try
            {
                var submitted = _client.Submit(Value(_session, "id", "Id"), _answers);
                if (!Convert.ToBoolean(submitted.ContainsKey("success") ? submitted["success"] : false))
                {
                    throw new InvalidOperationException(JsonUtil.Text(submitted.ContainsKey("message") ? submitted["message"] : "The LAN server rejected the submission."));
                }
                _timer.Stop();
                _examMode = false;
                TopMost = false;
                MessageBox.Show("Exam submitted successfully.", "Submitted");
                ShowConnect();
            }
            catch (Exception ex)
            {
                _submitting = false;
                MessageBox.Show(ex.Message, "Submit failed");
            }
        }

        private void TimerTick(object sender, EventArgs e)
        {
            if (!_examMode || _session == null) return;
            TopMost = true;
            if (FormBorderStyle != FormBorderStyle.None) FormBorderStyle = FormBorderStyle.None;
            if (WindowState != FormWindowState.Maximized) WindowState = FormWindowState.Maximized;
            SaveCurrentAnswer(_questionPanel);
            try { _client.SaveAnswers(Value(_session, "id", "Id"), _answers); } catch { }
            if (_timeLabel != null) _timeLabel.Text = TimeText();
            DateTime ends;
            if (DateTime.TryParse(Value(_session, "ends_at", "EndsAt"), out ends) && DateTime.UtcNow >= ends.ToUniversalTime())
            {
                _client.Submit(Value(_session, "id", "Id"), _answers);
                _timer.Stop();
                _examMode = false;
                MessageBox.Show("Time is up. Your exam has been submitted.", "Time up");
                ShowConnect();
            }
        }

        private void MainFormDeactivate(object sender, EventArgs e)
        {
            if (!_examMode || _session == null) return;
            if (_calculatorOpen) return;
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
            MessageBox.Show("Exam is still running. Submit the exam before closing this app.", "Exam running", MessageBoxButtons.OK, MessageBoxIcon.Warning);
        }

        private void ShowCalculator()
        {
            _calculatorOpen = true;
            var form = new Form { Text = "Calculator", Width = 360, Height = 210, StartPosition = FormStartPosition.CenterParent, TopMost = true, FormBorderStyle = FormBorderStyle.FixedDialog, MaximizeBox = false, MinimizeBox = false };
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
            var input = new TextBox { Left = 16, Top = 16, Width = 310, Font = new Font("Segoe UI", 13) };
            var result = Label("", 16, 100, 12, true, 310, Palette.Text);
            var solve = PrimaryButton("Calculate", 16, 54, 110);
            var clear = SecondaryButton("Clear", 138, 54, 80);
            clear.Click += (s, e) => { input.Text = ""; result.Text = ""; };
            solve.Click += (s, e) =>
            {
                try { result.Text = Convert.ToString(new System.Data.DataTable().Compute(input.Text, "")); }
                catch { result.Text = "Invalid"; }
            };
            form.Controls.Add(input); form.Controls.Add(solve); form.Controls.Add(clear); form.Controls.Add(result);
            form.Show(this);
        }

        private string TimeText()
        {
            DateTime ends;
            if (_session == null || !DateTime.TryParse(Value(_session, "ends_at", "EndsAt"), out ends)) return "";
            var span = ends.ToUniversalTime() - DateTime.UtcNow;
            if (span.TotalSeconds < 0) span = TimeSpan.Zero;
            return "Time: " + ((int)span.TotalHours).ToString("00") + ":" + span.Minutes.ToString("00") + ":" + span.Seconds.ToString("00");
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
        private Label Label(string text, int left, int top, int size, bool bold, int width, Color color) { return new Label { Text = text, Left = left, Top = top, AutoSize = true, MaximumSize = new Size(width, 0), Font = new Font("Segoe UI", size, bold ? FontStyle.Bold : FontStyle.Regular), ForeColor = color, UseCompatibleTextRendering = true }; }
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
