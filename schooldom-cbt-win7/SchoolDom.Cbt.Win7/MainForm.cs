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
        private readonly LanServerService _lan;
        private Panel _root;
        private Label _statusLabel;

        public MainForm()
        {
            _store = new LocalStore();
            _packages = new PackageService(_store);
            _cloud = new CloudSyncService(_store, _packages);
            _lan = new LanServerService(_store);

            // Require a fresh cloud login each time the admin opens the app.
            _store.State.AccessToken = "";
            _store.Save();

            Text = "SchoolDom Admin Sync Win7";
            Width = 1280;
            Height = 760;
            MinimumSize = new Size(1120, 680);
            StartPosition = FormStartPosition.CenterScreen;
            BackColor = Palette.Background;
            Font = new Font("Segoe UI", 10);
            AutoScaleMode = AutoScaleMode.Dpi;
            Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath);

            _root = new Panel { Dock = DockStyle.Fill };
            Controls.Add(_root);
            ShowCloudLogin();
        }

        private void ShowCloudLogin()
        {
            _root.Controls.Clear();

            var hero = new Panel { Dock = DockStyle.Left, Width = 430, BackColor = Palette.Navy };
            hero.Controls.Add(new Label
            {
                Text = "SchoolDom",
                Left = 38,
                Top = 46,
                Width = 320,
                Height = 40,
                ForeColor = Color.White,
                Font = new Font("Segoe UI", 22, FontStyle.Bold)
            });
            hero.Controls.Add(new Label
            {
                Text = "Admin Sync Console",
                Left = 40,
                Top = 92,
                Width = 320,
                Height = 28,
                ForeColor = Palette.SoftText,
                Font = new Font("Segoe UI", 12, FontStyle.Regular)
            });
            hero.Controls.Add(new Label
            {
                Text = "Cloud login is required on every launch. After login, the app automatically downloads published exams, students, and package metadata.",
                Left = 40,
                Top = 210,
                Width = 340,
                Height = 110,
                ForeColor = Palette.SoftText,
                Font = new Font("Segoe UI", 10, FontStyle.Regular)
            });

            var content = new Panel { Dock = DockStyle.Fill, BackColor = Palette.Background };
            var card = Card(82, 90, 560, 440);
            content.Controls.Add(card);

            card.Controls.Add(TextLabel("Cloud Login", 32, 28, 22, true, 460, Palette.Text));
            card.Controls.Add(TextLabel("Use an admin, principal, super admin, teacher, or accountant account with CBT sync permission.", 34, 68, 10, false, 485, Palette.Muted));

            var url = Field(card, "Cloud URL", _store.State.CloudUrl ?? "https://schooldom.academy", 34, 124, false);
            var email = Field(card, "Email", "", 34, 194, false);
            var password = Field(card, "Password", "", 294, 194, true);
            var schoolCode = Field(card, "School Code", "", 34, 264, false);

            _statusLabel = TextLabel("", 34, 380, 10, false, 490, Palette.Muted);
            card.Controls.Add(_statusLabel);

            var login = PrimaryButton("Login and Sync", 34, 324, 180);
            login.Click += (s, e) =>
            {
                RunWithStatus("Signing in and pulling school data...", () =>
                {
                    _cloud.Login(url.Text, email.Text, password.Text, schoolCode.Text);
                    return _cloud.PullPackage("");
                }, ShowDashboard);
            };
            card.Controls.Add(login);

            var token = SecondaryButton("Use JWT Token", 226, 324, 160);
            token.Click += (s, e) =>
            {
                var accessToken = PromptDialog.Show("JWT Access Token", "Paste admin JWT access token.", true);
                if (string.IsNullOrWhiteSpace(accessToken)) return;
                RunWithStatus("Saving token and pulling school data...", () =>
                {
                    _cloud.SaveToken(url.Text, accessToken);
                    return _cloud.PullPackage("");
                }, ShowDashboard);
            };
            card.Controls.Add(token);

            var offline = SecondaryButton("Offline Tools", 398, 324, 120);
            offline.Click += (s, e) => ShowDashboard();
            card.Controls.Add(offline);

            _root.Controls.Add(content);
            _root.Controls.Add(hero);
        }

        private void ShowDashboard()
        {
            _root.Controls.Clear();

            var sidebar = new Panel { Dock = DockStyle.Left, Width = 250, BackColor = Palette.Navy };
            sidebar.Controls.Add(TextLabel("SchoolDom", 24, 28, 20, true, 200, Color.White));
            sidebar.Controls.Add(TextLabel("Admin Sync", 26, 64, 10, false, 180, Palette.SoftText));

            var syncNow = SideButton("Sync Now", 24, 132);
            syncNow.Click += (s, e) => RunWithStatus("Pulling latest school data...", () => _cloud.PullPackage(""), ShowDashboard);
            sidebar.Controls.Add(syncNow);

            var upload = SideButton("Upload Results", 24, 186);
            upload.Click += (s, e) => RunWithStatus("Uploading local results...", () => _cloud.UploadResults(), ShowDashboard);
            sidebar.Controls.Add(upload);

            var broadsheet = SideButton("Broadsheet", 24, 240);
            broadsheet.Click += ExportBroadsheet;
            sidebar.Controls.Add(broadsheet);

            var lanStart = SideButton("Start LAN", 24, 294);
            lanStart.Click += (s, e) =>
            {
                try
                {
                    MessageBox.Show(_lan.Start(), "LAN Server");
                    ShowDashboard();
                }
                catch (Exception ex)
                {
                    MessageBox.Show(ex.Message, "LAN Server Failed");
                }
            };
            sidebar.Controls.Add(lanStart);

            var lanStop = SideButton("Stop LAN", 24, 348);
            lanStop.Click += (s, e) =>
            {
                MessageBox.Show(_lan.Stop(), "LAN Server");
                ShowDashboard();
            };
            sidebar.Controls.Add(lanStop);

            var import = SideButton("Import JSON", 24, 402);
            import.Click += ImportPackage;
            sidebar.Controls.Add(import);

            var export = SideButton("Export Results", 24, 456);
            export.Click += ExportResults;
            sidebar.Controls.Add(export);

            var signOut = SideButton("Sign Out", 24, 610);
            signOut.Click += (s, e) =>
            {
                _store.State.AccessToken = "";
                _store.Save();
                ShowCloudLogin();
            };
            sidebar.Controls.Add(signOut);

            var content = new Panel { Dock = DockStyle.Fill, BackColor = Palette.Background, AutoScroll = true };
            content.Controls.Add(TextLabel(DisplaySchoolName(), 34, 18, 20, true, 600, Palette.Text));
            content.Controls.Add(TextLabel("School data synced from SchoolDom cloud.", 36, 62, 10, false, 560, Palette.Muted));

            var status = TextLabel("Cloud: " + (_store.State.CloudUrl ?? "") + "\r\nLast sync: " + Display(_store.State.LastSyncAt), 650, 26, 9, false, 330, Palette.Muted);
            content.Controls.Add(status);

            content.Controls.Add(Metric("Published Exams", _store.State.Exams.Count.ToString(), 34, 112, Palette.Blue));
            content.Controls.Add(Metric("Students Cached", _store.State.Students.Count.ToString(), 290, 112, Palette.Green));
            content.Controls.Add(Metric("Local Sessions", _store.State.Sessions.Count.ToString(), 546, 112, Palette.Gold));
            content.Controls.Add(Metric("Submitted Results", _store.State.Sessions.Count(x => x.Status == "submitted").ToString(), 34, 202, Palette.Coral));
            content.Controls.Add(Metric("LAN Server", _lan.IsRunning ? "On" : "Off", 290, 202, _lan.IsRunning ? Palette.Green : Palette.Coral));
            content.Controls.Add(Metric("Package", string.IsNullOrWhiteSpace(_store.State.ActivePackageId) ? "None" : "Ready", 546, 202, Palette.Blue));

            var lan = Card(34, 306, 760, 104);
            lan.Controls.Add(TextLabel("Admin LAN Starter", 22, 14, 13, true, 260, Palette.Text));
            var lanText = _lan.IsRunning ? _lan.SnapshotMessage() : "LAN server is stopped. Start it to share cached school data on this network.";
            lan.Controls.Add(TextLabel(lanText, 22, 44, 9, false, 560, _lan.IsRunning ? Palette.Green : Palette.Muted));
            var lanStartInline = MiniButton(_lan.IsRunning ? "Restart" : "Start", 600, 32, 76);
            lanStartInline.Click += (s, e) =>
            {
                try
                {
                    if (_lan.IsRunning) _lan.Stop();
                    MessageBox.Show(_lan.Start(), "LAN Server");
                    ShowDashboard();
                }
                catch (Exception ex)
                {
                    MessageBox.Show(ex.Message, "LAN Server Failed");
                }
            };
            lan.Controls.Add(lanStartInline);
            var lanStopInline = MiniButton("Stop", 684, 32, 62);
            lanStopInline.Enabled = _lan.IsRunning;
            lanStopInline.Click += (s, e) =>
            {
                MessageBox.Show(_lan.Stop(), "LAN Server");
                ShowDashboard();
            };
            lan.Controls.Add(lanStopInline);
            content.Controls.Add(lan);

            var exams = Card(34, 432, 500, 410);
            exams.Controls.Add(TextLabel("Exams", 22, 18, 16, true, 240, Palette.Text));
            var moreExams = MiniButton("More", 408, 18, 74);
            moreExams.Click += (s, e) => ShowExamList();
            exams.Controls.Add(moreExams);
            FillExamList(exams);
            content.Controls.Add(exams);

            var students = Card(558, 432, 500, 410);
            students.Controls.Add(TextLabel("Students", 22, 18, 16, true, 240, Palette.Text));
            var moreStudents = MiniButton("More", 408, 18, 74);
            moreStudents.Click += (s, e) => ShowStudentList();
            students.Controls.Add(moreStudents);
            FillStudentList(students);
            content.Controls.Add(students);

            var note = Card(34, 866, 1024, 96);
            note.Controls.Add(TextLabel("Admin Sync Tools", 22, 16, 14, true, 940, Palette.Text));
            note.Controls.Add(TextLabel("Use this console to sync school CBT data, review/edit imported exams, export broadsheets, and upload or export local result packages.", 22, 48, 10, false, 960, Palette.Muted));
            content.Controls.Add(note);

            _root.Controls.Add(content);
            _root.Controls.Add(sidebar);
        }

        private void FillExamList(Panel card)
        {
            var y = 58;
            foreach (var exam in _store.State.Exams.Take(5))
            {
                card.Controls.Add(TextLabel(exam.Title, 22, y, 10, true, 250, Palette.Text));
                card.Controls.Add(TextLabel((exam.Subject ?? "") + "  " + Math.Max(1, exam.Questions.Count) + " question(s)", 22, y + 28, 9, false, 300, Palette.Muted));
                var review = MiniButton("Review", 326, y, 84);
                review.Click += (s, e) => ShowExamReview(exam);
                card.Controls.Add(review);
                var edit = MiniButton("Edit", 416, y, 64);
                edit.Click += (s, e) => ShowExamEditor(exam);
                card.Controls.Add(edit);
                y += 74;
            }
            if (!_store.State.Exams.Any())
            {
                card.Controls.Add(TextLabel("No exams have been pulled yet.", 22, 64, 10, false, 430, Palette.Muted));
            }
        }

        private void FillStudentList(Panel card)
        {
            var y = 58;
            foreach (var student in _store.State.Students.Take(5))
            {
                card.Controls.Add(TextLabel(student.FullName, 22, y, 10, true, 440, Palette.Text));
                card.Controls.Add(TextLabel(student.StudentId + "  " + (student.ClassName ?? ""), 22, y + 30, 9, false, 440, Palette.Muted));
                y += 70;
            }
            if (!_store.State.Students.Any())
            {
                card.Controls.Add(TextLabel("No students have been pulled yet.", 22, 64, 10, false, 430, Palette.Muted));
            }
        }

        private void ShowExamList()
        {
            using (var form = ListForm("All Exams", 760, 540))
            {
                var list = new ListView { Dock = DockStyle.Fill, View = View.Details, FullRowSelect = true };
                list.Columns.Add("Title", 250);
                list.Columns.Add("Subject", 150);
                list.Columns.Add("Class", 120);
                list.Columns.Add("Questions", 80);
                foreach (var exam in _store.State.Exams.OrderBy(e => e.Title))
                {
                    var item = new ListViewItem(exam.Title);
                    item.SubItems.Add(exam.Subject ?? "");
                    item.SubItems.Add(exam.ClassName ?? "");
                    item.SubItems.Add(exam.Questions.Count.ToString());
                    item.Tag = exam;
                    list.Items.Add(item);
                }
                list.DoubleClick += (s, e) =>
                {
                    if (list.SelectedItems.Count == 0) return;
                    ShowExamReview((ExamRecord)list.SelectedItems[0].Tag);
                };
                var edit = PrimaryButton("Edit Selected", 12, 458, 130);
                edit.Anchor = AnchorStyles.Left | AnchorStyles.Bottom;
                edit.Click += (s, e) =>
                {
                    if (list.SelectedItems.Count == 0) return;
                    ShowExamEditor((ExamRecord)list.SelectedItems[0].Tag);
                    form.Close();
                };
                var panel = new Panel { Dock = DockStyle.Bottom, Height = 58 };
                panel.Controls.Add(edit);
                form.Controls.Add(list);
                form.Controls.Add(panel);
                form.ShowDialog(this);
            }
        }

        private void ShowStudentList()
        {
            using (var form = ListForm("All Students", 760, 540))
            {
                var list = new ListView { Dock = DockStyle.Fill, View = View.Details, FullRowSelect = true };
                list.Columns.Add("Name", 280);
                list.Columns.Add("Student ID", 140);
                list.Columns.Add("Class", 180);
                foreach (var student in _store.State.Students.OrderBy(s => s.FullName))
                {
                    var item = new ListViewItem(student.FullName);
                    item.SubItems.Add(student.StudentId ?? "");
                    item.SubItems.Add(student.ClassName ?? "");
                    list.Items.Add(item);
                }
                form.Controls.Add(list);
                form.ShowDialog(this);
            }
        }

        private void ShowExamReview(ExamRecord exam)
        {
            using (var form = ListForm("Review: " + exam.Title, 860, 620))
            {
                var text = new TextBox
                {
                    Dock = DockStyle.Fill,
                    Multiline = true,
                    ReadOnly = true,
                    ScrollBars = ScrollBars.Vertical,
                    Font = new Font("Consolas", 10),
                    Text = BuildExamReviewText(exam)
                };
                form.Controls.Add(text);
                form.ShowDialog(this);
            }
        }

        private string BuildExamReviewText(ExamRecord exam)
        {
            var lines = new System.Text.StringBuilder();
            lines.AppendLine(exam.Title);
            lines.AppendLine("Subject: " + exam.Subject);
            lines.AppendLine("Class: " + exam.ClassName);
            lines.AppendLine("Duration: " + Math.Max(1, exam.DurationSeconds / 60) + " minutes");
            lines.AppendLine();
            lines.AppendLine("Instructions:");
            lines.AppendLine(exam.Instructions ?? "");
            lines.AppendLine();
            for (var i = 0; i < exam.Questions.Count; i++)
            {
                var q = exam.Questions[i];
                lines.AppendLine((i + 1) + ". " + q.Text);
                for (var j = 0; j < q.Options.Count; j++)
                {
                    lines.AppendLine("   " + (char)('A' + j) + ". " + q.Options[j]);
                }
                lines.AppendLine();
            }
            return lines.ToString();
        }

        private void ShowExamEditor(ExamRecord exam)
        {
            using (var form = ListForm("Edit Exam", 560, 480))
            {
                var title = Field(form, "Title", exam.Title, 28, 64, false);
                title.Width = 480;
                var subject = Field(form, "Subject", exam.Subject, 28, 134, false);
                var className = Field(form, "Class", exam.ClassName, 288, 134, false);
                var duration = Field(form, "Duration Minutes", Math.Max(1, exam.DurationSeconds / 60).ToString(), 28, 204, false);
                var instructionsLabel = TextLabel("Instructions", 28, 254, 9, true, 220, Palette.Text);
                form.Controls.Add(instructionsLabel);
                var instructions = new TextBox
                {
                    Left = 28,
                    Top = 276,
                    Width = 480,
                    Height = 88,
                    Multiline = true,
                    ScrollBars = ScrollBars.Vertical,
                    Text = exam.Instructions ?? ""
                };
                form.Controls.Add(instructions);
                var save = PrimaryButton("Save Changes", 28, 390, 140);
                save.Click += (s, e) =>
                {
                    int minutes;
                    if (!int.TryParse(duration.Text, out minutes) || minutes < 1)
                    {
                        MessageBox.Show("Enter a valid duration in minutes.", "Edit Exam");
                        return;
                    }
                    exam.Title = title.Text.Trim();
                    exam.Subject = subject.Text.Trim();
                    exam.ClassName = className.Text.Trim();
                    exam.DurationSeconds = minutes * 60;
                    exam.Instructions = instructions.Text;
                    _packages.SaveExam(exam);
                    form.Close();
                    ShowDashboard();
                };
                form.Controls.Add(save);
                form.ShowDialog(this);
            }
        }

        private void RunWithStatus(string status, Func<string> action, Action onSuccess)
        {
            try
            {
                SetStatus(status, Palette.Muted);
                Cursor = Cursors.WaitCursor;
                var message = action();
                Cursor = Cursors.Default;
                SetStatus(message, Palette.Green);
                MessageBox.Show(message, "SchoolDom Sync");
                onSuccess();
            }
            catch (Exception ex)
            {
                Cursor = Cursors.Default;
                SetStatus(ex.Message, Palette.Coral);
                MessageBox.Show(ex.Message, "SchoolDom Sync Failed");
            }
        }

        private void SetStatus(string text, Color color)
        {
            if (_statusLabel == null) return;
            _statusLabel.Text = text;
            _statusLabel.ForeColor = color;
            _statusLabel.Refresh();
        }

        private void ImportPackage(object sender, EventArgs e)
        {
            using (var dialog = new OpenFileDialog())
            {
                dialog.Filter = "SchoolDom package (*.json)|*.json|All files (*.*)|*.*";
                if (dialog.ShowDialog(this) != DialogResult.OK) return;
                try
                {
                    MessageBox.Show(_packages.ImportPackage(dialog.FileName, ""), "Import complete");
                    ShowDashboard();
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
                    ShowDashboard();
                }
                catch (Exception ex)
                {
                    MessageBox.Show(ex.Message, "Export failed");
                }
            }
        }

        private void ExportBroadsheet(object sender, EventArgs e)
        {
            using (var dialog = new SaveFileDialog())
            {
                dialog.Filter = "CSV broadsheet (*.csv)|*.csv";
                dialog.FileName = "schooldom-broadsheet-" + DateTime.Now.ToString("yyyyMMddHHmmss") + ".csv";
                if (dialog.ShowDialog(this) != DialogResult.OK) return;
                try
                {
                    MessageBox.Show(_packages.ExportBroadsheet(dialog.FileName), "Broadsheet");
                }
                catch (Exception ex)
                {
                    MessageBox.Show(ex.Message, "Broadsheet failed");
                }
            }
        }

        private TextBox Field(Control parent, string label, string value, int left, int top, bool password)
        {
            parent.Controls.Add(TextLabel(label, left, top - 22, 9, true, 220, Palette.Text));
            var box = new TextBox
            {
                Left = left,
                Top = top,
                Width = 226,
                Height = 34,
                Text = value,
                UseSystemPasswordChar = password,
                Font = new Font("Segoe UI", 11),
                BorderStyle = BorderStyle.FixedSingle
            };
            parent.Controls.Add(box);
            return box;
        }

        private Panel Metric(string label, string value, int left, int top, Color accent)
        {
            var card = Card(left, top, 224, 84);
            var bar = new Panel { Left = 0, Top = 0, Width = 5, Height = 84, BackColor = accent };
            card.Controls.Add(bar);
            card.Controls.Add(TextLabel(label, 20, 12, 9, true, 180, Palette.Muted));
            card.Controls.Add(TextLabel(value, 20, 38, 20, true, 180, Palette.Text));
            return card;
        }

        private Button SideButton(string text, int left, int top)
        {
            var button = new Button
            {
                Text = text,
                Left = left,
                Top = top,
                Width = 198,
                Height = 42,
                FlatStyle = FlatStyle.Flat,
                BackColor = Palette.SideButton,
                ForeColor = Color.White,
                Font = new Font("Segoe UI", 10, FontStyle.Bold),
                TextAlign = ContentAlignment.MiddleLeft,
                Padding = new Padding(14, 0, 0, 0)
            };
            button.FlatAppearance.BorderColor = Palette.SideButton;
            return button;
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

        private Label TextLabel(string text, int left, int top, int size, bool bold, int width, Color color)
        {
            var lineCount = Math.Max(1, ((text ?? "").Length / Math.Max(18, width / 8)) + 1);
            var height = Math.Max(size * 3 + 10, lineCount * (size + 12));
            return new Label
            {
                Text = text,
                Left = left,
                Top = top,
                Width = width,
                Height = height,
                Font = new Font("Segoe UI", size, bold ? FontStyle.Bold : FontStyle.Regular),
                ForeColor = color
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
                BackColor = Palette.Blue,
                ForeColor = Color.White,
                FlatStyle = FlatStyle.Flat,
                Font = new Font("Segoe UI", 10, FontStyle.Bold)
            };
            button.FlatAppearance.BorderColor = Palette.Blue;
            return button;
        }

        private Button SecondaryButton(string text, int left, int top, int width)
        {
            var button = PrimaryButton(text, left, top, width);
            button.BackColor = Palette.LightButton;
            button.ForeColor = Palette.Text;
            button.FlatAppearance.BorderColor = Palette.Border;
            return button;
        }

        private Button MiniButton(string text, int left, int top, int width)
        {
            var button = SecondaryButton(text, left, top, width);
            button.Height = 28;
            button.Font = new Font("Segoe UI", 8, FontStyle.Bold);
            return button;
        }

        private Form ListForm(string title, int width, int height)
        {
            return new Form
            {
                Text = title,
                Width = width,
                Height = height,
                StartPosition = FormStartPosition.CenterParent,
                BackColor = Palette.Background,
                Font = new Font("Segoe UI", 10)
            };
        }

        private string Display(string value)
        {
            return string.IsNullOrWhiteSpace(value) ? "Not available" : value;
        }

        private string DisplaySchoolName()
        {
            return string.IsNullOrWhiteSpace(_store.State.SchoolName) ? "School Data Sync" : _store.State.SchoolName;
        }
    }

    internal static class Palette
    {
        public static readonly Color Background = Color.FromArgb(244, 247, 251);
        public static readonly Color Navy = Color.FromArgb(15, 32, 55);
        public static readonly Color SideButton = Color.FromArgb(31, 55, 87);
        public static readonly Color Text = Color.FromArgb(22, 34, 51);
        public static readonly Color Muted = Color.FromArgb(96, 112, 132);
        public static readonly Color SoftText = Color.FromArgb(196, 207, 221);
        public static readonly Color Border = Color.FromArgb(214, 223, 235);
        public static readonly Color LightButton = Color.FromArgb(235, 241, 248);
        public static readonly Color Blue = Color.FromArgb(24, 96, 180);
        public static readonly Color Green = Color.FromArgb(37, 137, 92);
        public static readonly Color Gold = Color.FromArgb(184, 127, 33);
        public static readonly Color Coral = Color.FromArgb(196, 74, 62);
    }
}
