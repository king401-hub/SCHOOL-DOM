using System;
using System.Drawing;
using System.Linq;
using System.Windows.Forms;

namespace SchoolDom.Cbt.Win7
{
    public class MainForm : Form
    {
        private readonly LocalStore _store;
        private readonly PackageService _packages;
        private readonly CloudSyncService _cloud;
        private readonly Timer _timer;
        private Panel _root;
        private StudentRecord _activeStudent;
        private ExamRecord _activeExam;
        private SessionRecord _activeSession;
        private int _questionIndex;

        public MainForm()
        {
            _store = new LocalStore();
            _packages = new PackageService(_store);
            _cloud = new CloudSyncService(_store, _packages);
            _timer = new Timer { Interval = 1000 };
            _timer.Tick += TimerTick;

            Text = "SchoolDom Student CBT";
            Width = 1180;
            Height = 760;
            MinimumSize = new Size(980, 640);
            StartPosition = FormStartPosition.CenterScreen;
            BackColor = Color.FromArgb(246, 248, 252);
            Font = new Font("Segoe UI", 10);

            _root = new Panel { Dock = DockStyle.Fill };
            Controls.Add(_root);
            FormClosing += MainFormClosing;
            Deactivate += MainFormDeactivate;
            ShowLogin();
        }

        private void Shell(string title, Action<Panel> body)
        {
            _root.Controls.Clear();
            var header = new Panel { Dock = DockStyle.Top, Height = 72, BackColor = Color.White };
            var heading = new Label
            {
                Text = title,
                Font = new Font("Segoe UI", 18, FontStyle.Bold),
                ForeColor = Color.FromArgb(20, 31, 52),
                Left = 24,
                Top = 18,
                Width = 520
            };
            var admin = HeaderButton("Admin", 760, ShowAdmin);
            var login = HeaderButton("Student Login", 856, ShowLogin);
            var exit = HeaderButton("Exit", 1010, Close);
            header.Controls.Add(heading);
            header.Controls.Add(admin);
            header.Controls.Add(login);
            header.Controls.Add(exit);

            var content = new Panel { Dock = DockStyle.Fill, Padding = new Padding(24), AutoScroll = true };
            _root.Controls.Add(content);
            _root.Controls.Add(header);
            body(content);
        }

        private Button HeaderButton(string text, int left, Action action)
        {
            var button = new Button
            {
                Text = text,
                Left = left,
                Top = 18,
                Width = text.Length > 8 ? 140 : 84,
                Height = 36,
                FlatStyle = FlatStyle.Flat,
                BackColor = Color.FromArgb(238, 243, 250)
            };
            button.FlatAppearance.BorderColor = Color.FromArgb(213, 222, 235);
            button.Click += (s, e) => action();
            return button;
        }

        private void ShowAdmin()
        {
            _timer.Stop();
            TopMost = false;
            FormBorderStyle = FormBorderStyle.Sizable;
            WindowState = FormWindowState.Normal;
            Shell("Admin Control", panel =>
            {
                var card = Card(24, 24, 720, 330);
                panel.Controls.Add(card);

                card.Controls.Add(Label("Offline package", 24, 22, 18, true, 500));
                card.Controls.Add(Label("Import exams and students, then export completed results after the exam.", 24, 56, 10, false, 620));

                var import = PrimaryButton("Import Package", 24, 98, 180);
                import.Click += ImportPackage;
                card.Controls.Add(import);

                var export = PrimaryButton("Export Results", 214, 98, 180);
                export.Click += ExportResults;
                card.Controls.Add(export);

                var cloudPull = PrimaryButton("Pull From Cloud", 404, 98, 180);
                cloudPull.Click += PullFromCloud;
                card.Controls.Add(cloudPull);

                var cloudPush = PrimaryButton("Upload Results", 24, 150, 180);
                cloudPush.Click += UploadResults;
                card.Controls.Add(cloudPush);

                var token = SecondaryButton("Set Token", 214, 150, 180);
                token.Click += SetCloudToken;
                card.Controls.Add(token);

                var login = SecondaryButton("Cloud Login", 404, 150, 180);
                login.Click += CloudLogin;
                card.Controls.Add(login);

                var stats = "Exams: " + _store.State.Exams.Count +
                            "\r\nStudents: " + _store.State.Students.Count +
                            "\r\nSessions: " + _store.State.Sessions.Count +
                            "\r\nSubmitted: " + _store.State.Sessions.Count(s => s.Status == "submitted") +
                            "\r\nCloud: " + (_store.State.CloudUrl ?? "") +
                            "\r\nLast sync: " + (_store.State.LastSyncAt ?? "") +
                            "\r\nPackage: " + (_store.State.ActivePackageId ?? "");
                card.Controls.Add(Label(stats, 24, 210, 10, false, 660));

                var note = Card(24, 380, 720, 150);
                panel.Controls.Add(note);
                note.Controls.Add(Label("Windows 7 note", 24, 22, 16, true, 500));
                note.Controls.Add(Label("Package import/export remains the safest exam workflow. Direct online sync uses TLS 1.2 and may require Windows 7 SP1 updates and current root certificates.", 24, 58, 10, false, 650));
            });
        }

        private void ShowLogin()
        {
            _timer.Stop();
            Shell("Student Login", panel =>
            {
                var card = Card(24, 24, 560, 330);
                panel.Controls.Add(card);
                card.Controls.Add(Label("Start or resume exam", 24, 24, 18, true, 480));
                card.Controls.Add(Label("Enter your Student ID and the exam PIN given by the school.", 24, 58, 10, false, 500));

                var studentId = TextInput(24, 110, 360);
                var pin = TextInput(24, 174, 360);
                pin.UseSystemPasswordChar = true;
                card.Controls.Add(Label("Student ID", 24, 88, 10, true, 200));
                card.Controls.Add(studentId);
                card.Controls.Add(Label("Exam PIN", 24, 152, 10, true, 200));
                card.Controls.Add(pin);

                var start = PrimaryButton("Start Exam", 24, 238, 150);
                start.Click += (s, e) =>
                {
                    var student = _store.FindStudent(studentId.Text);
                    if (student == null)
                    {
                        MessageBox.Show("Student ID was not found on this computer.", "Login failed");
                        return;
                    }
                    var exam = _store.FindExamByPin(pin.Text);
                    if (exam == null)
                    {
                        MessageBox.Show("Invalid exam PIN.", "Login failed");
                        return;
                    }
                    _activeStudent = student;
                    _activeExam = exam;
                    _activeSession = _store.StartOrResumeSession(exam, student);
                    if (_activeSession.Status == "submitted")
                    {
                        MessageBox.Show("This exam has already been submitted on this computer.", "Already submitted");
                        return;
                    }
                    _questionIndex = 0;
                    ShowExam();
                };
                card.Controls.Add(start);

                var status = Card(620, 24, 360, 190);
                panel.Controls.Add(status);
                status.Controls.Add(Label("Loaded data", 24, 22, 16, true, 300));
                status.Controls.Add(Label(_store.State.Exams.Count + " exam(s)\r\n" + _store.State.Students.Count + " student(s)\r\n" + _store.State.Sessions.Count(s => s.Status == "submitted") + " submitted result(s)", 24, 58, 10, false, 300));
            });
        }

        private void ShowExam()
        {
            if (_activeExam == null || _activeStudent == null || _activeSession == null) return;
            _timer.Start();
            TopMost = true;
            FormBorderStyle = FormBorderStyle.None;
            WindowState = FormWindowState.Maximized;
            ExamShell(_activeExam.Title, panel =>
            {
                var side = Card(24, 24, 240, 560);
                var main = Card(288, 24, 780, 560);
                panel.Controls.Add(side);
                panel.Controls.Add(main);

                side.Controls.Add(Label(_activeStudent.FullName, 18, 18, 13, true, 210));
                side.Controls.Add(Label(_activeStudent.StudentId + "\r\n" + _activeExam.Subject, 18, 46, 9, false, 210));
                side.Controls.Add(Label("Questions", 18, 96, 11, true, 210));

                var y = 128;
                for (var i = 0; i < _activeExam.Questions.Count; i++)
                {
                    var index = i;
                    var btn = new Button
                    {
                        Text = (i + 1).ToString(),
                        Left = 18 + (i % 5) * 42,
                        Top = y + (i / 5) * 42,
                        Width = 34,
                        Height = 34,
                        FlatStyle = FlatStyle.Flat,
                        BackColor = _activeSession.Answers.ContainsKey(_activeExam.Questions[i].Id)
                            ? Color.FromArgb(198, 232, 215)
                            : Color.FromArgb(238, 243, 250)
                    };
                    if (i == _questionIndex) btn.BackColor = Color.FromArgb(24, 96, 180);
                    btn.ForeColor = i == _questionIndex ? Color.White : Color.FromArgb(20, 31, 52);
                    btn.Click += (s, e) => { SaveCurrentAnswer(main); _questionIndex = index; ShowExam(); };
                    side.Controls.Add(btn);
                }

                var submit = PrimaryButton("Submit Exam", 18, 492, 200);
                submit.Click += (s, e) => SubmitExam();
                side.Controls.Add(submit);

                RenderQuestion(main);
            });
        }

        private void ExamShell(string title, Action<Panel> body)
        {
            _root.Controls.Clear();
            var header = new Panel { Dock = DockStyle.Top, Height = 64, BackColor = Color.FromArgb(20, 31, 52) };
            var heading = new Label
            {
                Text = title,
                Font = new Font("Segoe UI", 17, FontStyle.Bold),
                ForeColor = Color.White,
                Left = 24,
                Top = 16,
                Width = 720
            };
            var timer = new Label
            {
                Text = TimeRemainingText(),
                Font = new Font("Segoe UI", 13, FontStyle.Bold),
                ForeColor = Color.White,
                Left = Width - 260,
                Top = 20,
                Width = 220
            };
            header.Controls.Add(heading);
            header.Controls.Add(timer);
            var content = new Panel { Dock = DockStyle.Fill, Padding = new Padding(24), AutoScroll = true };
            _root.Controls.Add(content);
            _root.Controls.Add(header);
            body(content);
        }

        private void RenderQuestion(Panel main)
        {
            main.Controls.Clear();
            var question = _activeExam.Questions[_questionIndex];
            main.Controls.Add(Label("Question " + (_questionIndex + 1) + " of " + _activeExam.Questions.Count, 24, 20, 11, true, 360));
            main.Controls.Add(Label(TimeRemainingText(), 590, 20, 11, true, 160));

            var top = 58;
            if (question.Group != null && !string.IsNullOrWhiteSpace(question.Group.PassageText))
            {
                var passage = Label(question.Group.PassageText, 24, top, 10, false, 720);
                passage.Height = 86;
                passage.BackColor = Color.FromArgb(247, 250, 255);
                passage.BorderStyle = BorderStyle.FixedSingle;
                main.Controls.Add(passage);
                top += 104;
            }

            var qText = Label(question.Text, 24, top, 13, true, 720);
            qText.Height = 86;
            main.Controls.Add(qText);
            top += 100;

            if (question.Type == "essay" || question.Type == "theory" || question.Type == "fill_blank" || question.Type == "fill_in_the_blank")
            {
                var answer = new TextBox { Left = 24, Top = top, Width = 720, Height = 170, Multiline = true, ScrollBars = ScrollBars.Vertical, Tag = "answer" };
                object saved;
                if (_activeSession.Answers.TryGetValue(question.Id, out saved)) answer.Text = Convert.ToString(saved);
                main.Controls.Add(answer);
            }
            else
            {
                var options = question.Options.Count > 0 ? question.Options : new System.Collections.Generic.List<string> { "True", "False" };
                for (var i = 0; i < options.Count; i++)
                {
                    var option = new RadioButton
                    {
                        Left = 30,
                        Top = top + i * 46,
                        Width = 700,
                        Height = 36,
                        Text = ((char)('A' + i)) + ". " + options[i],
                        Tag = "answer:" + i,
                        Font = new Font("Segoe UI", 11)
                    };
                    object saved;
                    option.Checked = _activeSession.Answers.TryGetValue(question.Id, out saved) && Convert.ToString(saved) == Convert.ToString(i);
                    option.CheckedChanged += (s, e) => SaveCurrentAnswer(main);
                    main.Controls.Add(option);
                }
            }

            var prev = SecondaryButton("Previous", 24, 492, 120);
            prev.Enabled = _questionIndex > 0;
            prev.Click += (s, e) => { SaveCurrentAnswer(main); _questionIndex--; ShowExam(); };
            var next = PrimaryButton(_questionIndex == _activeExam.Questions.Count - 1 ? "Review" : "Next", 154, 492, 120);
            next.Click += (s, e) =>
            {
                SaveCurrentAnswer(main);
                if (_questionIndex < _activeExam.Questions.Count - 1) _questionIndex++;
                ShowExam();
            };
            main.Controls.Add(prev);
            main.Controls.Add(next);
        }

        private void SaveCurrentAnswer(Control container)
        {
            if (_activeSession == null || _activeExam == null || _activeExam.Questions.Count == 0) return;
            var question = _activeExam.Questions[_questionIndex];
            SaveCurrentAnswerFromControls(container, question);
            _store.Save();
        }

        private void SaveCurrentAnswerFromControls(Control container, QuestionRecord question)
        {
            foreach (Control control in container.Controls)
            {
                if (control.HasChildren) SaveCurrentAnswerFromControls(control, question);
                if (control.Tag == null) continue;
                var tag = Convert.ToString(control.Tag);
                if (tag == "answer" && control is TextBox)
                {
                    var text = ((TextBox)control).Text;
                    if (string.IsNullOrWhiteSpace(text)) _activeSession.Answers.Remove(question.Id);
                    else _activeSession.Answers[question.Id] = text;
                }
                if (tag.StartsWith("answer:") && control is RadioButton && ((RadioButton)control).Checked)
                {
                    _activeSession.Answers[question.Id] = tag.Substring("answer:".Length);
                }
            }
        }

        private void SubmitExam()
        {
            SaveCurrentAnswer(_root);
            var answered = _activeSession.Answers.Count;
            var total = _activeExam.Questions.Count;
            var confirm = MessageBox.Show("You answered " + answered + " of " + total + " questions. Submit now?", "Submit exam", MessageBoxButtons.YesNo, MessageBoxIcon.Question);
            if (confirm != DialogResult.Yes) return;
            _activeSession.Status = "submitted";
            _activeSession.SubmittedAt = JsonUtil.IsoNow();
            _activeSession.AuditLogs.Add(new ActivityLogRecord
            {
                Type = "session_submitted",
                Message = "Exam was submitted locally.",
                CreatedAt = JsonUtil.IsoNow()
            });
            _store.Save();
            _timer.Stop();
            MessageBox.Show("Submission saved on this computer. The admin can export results now.", "Saved");
            ShowLogin();
        }

        private void TimerTick(object sender, EventArgs e)
        {
            if (_activeSession == null || _activeSession.Status == "submitted") return;
            SaveCurrentAnswer(_root);
            DateTime ends;
            if (DateTime.TryParse(_activeSession.EndsAt, out ends) && DateTime.UtcNow >= ends.ToUniversalTime())
            {
                _activeSession.Status = "submitted";
                _activeSession.SubmittedAt = JsonUtil.IsoNow();
                _activeSession.AuditLogs.Add(new ActivityLogRecord
                {
                    Type = "timer_elapsed",
                    Message = "Exam auto-submitted when the timer reached zero.",
                    CreatedAt = JsonUtil.IsoNow()
                });
                _store.Save();
                _timer.Stop();
                MessageBox.Show("Time is up. Your exam has been submitted.", "Time up");
                ShowLogin();
                return;
            }
            _store.Save();
        }

        private void MainFormDeactivate(object sender, EventArgs e)
        {
            if (_activeSession == null || _activeSession.Status == "submitted") return;
            _activeSession.FocusLossCount += 1;
            _activeSession.AuditLogs.Add(new ActivityLogRecord
            {
                Type = "focus_loss",
                Message = "Student left the CBT window.",
                CreatedAt = JsonUtil.IsoNow()
            });
            _store.Save();
        }

        private void MainFormClosing(object sender, FormClosingEventArgs e)
        {
            if (_activeSession != null && _activeSession.Status != "submitted")
            {
                SaveCurrentAnswer(_root);
                var confirm = MessageBox.Show("An exam is still in progress. Closing will keep the saved session but should only be done by an invigilator. Close anyway?", "Exam in progress", MessageBoxButtons.YesNo, MessageBoxIcon.Warning);
                if (confirm != DialogResult.Yes)
                {
                    e.Cancel = true;
                    return;
                }
                _activeSession.AuditLogs.Add(new ActivityLogRecord
                {
                    Type = "forced_close",
                    Message = "Application was closed before submission.",
                    CreatedAt = JsonUtil.IsoNow()
                });
            }
            _store.Save();
        }

        private string TimeRemainingText()
        {
            DateTime ends;
            if (!DateTime.TryParse(_activeSession.EndsAt, out ends)) return "Timer unavailable";
            var span = ends.ToUniversalTime() - DateTime.UtcNow;
            if (span.TotalSeconds < 0) span = TimeSpan.Zero;
            return "Time: " + ((int)span.TotalHours).ToString("00") + ":" + span.Minutes.ToString("00") + ":" + span.Seconds.ToString("00");
        }

        private void ImportPackage(object sender, EventArgs e)
        {
            using (var dialog = new OpenFileDialog())
            {
                dialog.Filter = "SchoolDom package (*.json)|*.json|All files (*.*)|*.*";
                if (dialog.ShowDialog(this) != DialogResult.OK) return;
                var pin = PromptDialog.Show("Exam PIN", "Enter fallback exam PIN for offline validation.", true);
                try
                {
                    MessageBox.Show(_packages.ImportPackage(dialog.FileName, pin), "Import complete");
                    ShowAdmin();
                }
                catch (Exception ex)
                {
                    MessageBox.Show(ex.Message, "Import failed");
                }
            }
        }

        private void ExportResults(object sender, EventArgs e)
        {
            using (var dialog = new SaveFileDialog())
            {
                dialog.Filter = "SchoolDom results (*.json)|*.json";
                dialog.FileName = "schooldom-cbt-results-" + DateTime.Now.ToString("yyyyMMddHHmmss") + ".json";
                if (dialog.ShowDialog(this) != DialogResult.OK) return;
                try
                {
                    MessageBox.Show(_packages.ExportResults(dialog.FileName), "Export complete");
                    ShowAdmin();
                }
                catch (Exception ex)
                {
                    MessageBox.Show(ex.Message, "Export failed");
                }
            }
        }

        private void SetCloudToken(object sender, EventArgs e)
        {
            var url = PromptDialog.Show("Cloud URL", "SchoolDom cloud URL", false);
            if (string.IsNullOrWhiteSpace(url)) url = _store.State.CloudUrl;
            var token = PromptDialog.Show("JWT Access Token", "Paste admin JWT access token.", true);
            if (string.IsNullOrWhiteSpace(token)) return;
            _cloud.SaveToken(url, token);
            MessageBox.Show("Cloud token saved locally.", "Cloud");
            ShowAdmin();
        }

        private void CloudLogin(object sender, EventArgs e)
        {
            try
            {
                var url = PromptDialog.Show("Cloud URL", "SchoolDom cloud URL", false);
                if (string.IsNullOrWhiteSpace(url)) url = _store.State.CloudUrl;
                var email = PromptDialog.Show("Admin Email", "Admin or teacher email", false);
                var password = PromptDialog.Show("Password", "Password", true);
                var schoolCode = PromptDialog.Show("School Code", "School code, if required", false);
                MessageBox.Show(_cloud.Login(url, email, password, schoolCode), "Cloud");
                ShowAdmin();
            }
            catch (Exception ex)
            {
                MessageBox.Show(ex.Message, "Cloud login failed");
            }
        }

        private void PullFromCloud(object sender, EventArgs e)
        {
            try
            {
                var pin = PromptDialog.Show("Exam PIN", "Enter fallback exam PIN for offline validation.", true);
                MessageBox.Show(_cloud.PullPackage(pin), "Cloud pull complete");
                ShowAdmin();
            }
            catch (Exception ex)
            {
                MessageBox.Show(ex.Message, "Cloud pull failed");
            }
        }

        private void UploadResults(object sender, EventArgs e)
        {
            try
            {
                MessageBox.Show(_cloud.UploadResults(), "Cloud upload complete");
                ShowAdmin();
            }
            catch (Exception ex)
            {
                MessageBox.Show(ex.Message, "Cloud upload failed");
            }
        }

        private Panel Card(int left, int top, int width, int height)
        {
            return new Panel
            {
                Left = left,
                Top = top,
                Width = width,
                Height = height,
                BackColor = Color.White,
                BorderStyle = BorderStyle.FixedSingle
            };
        }

        private Label Label(string text, int left, int top, int size, bool bold, int width)
        {
            return new Label
            {
                Text = text,
                Left = left,
                Top = top,
                Width = width,
                Height = 26 + Math.Max(0, text.Length / 70) * 22,
                Font = new Font("Segoe UI", size, bold ? FontStyle.Bold : FontStyle.Regular),
                ForeColor = Color.FromArgb(20, 31, 52)
            };
        }

        private TextBox TextInput(int left, int top, int width)
        {
            return new TextBox
            {
                Left = left,
                Top = top,
                Width = width,
                Height = 34,
                Font = new Font("Segoe UI", 12)
            };
        }

        private Button PrimaryButton(string text, int left, int top, int width)
        {
            var button = new Button
            {
                Text = text,
                Left = left,
                Top = top,
                Width = width,
                Height = 42,
                BackColor = Color.FromArgb(24, 96, 180),
                ForeColor = Color.White,
                FlatStyle = FlatStyle.Flat
            };
            button.FlatAppearance.BorderColor = Color.FromArgb(24, 96, 180);
            return button;
        }

        private Button SecondaryButton(string text, int left, int top, int width)
        {
            var button = PrimaryButton(text, left, top, width);
            button.BackColor = Color.FromArgb(238, 243, 250);
            button.ForeColor = Color.FromArgb(20, 31, 52);
            button.FlatAppearance.BorderColor = Color.FromArgb(213, 222, 235);
            return button;
        }
    }
}
