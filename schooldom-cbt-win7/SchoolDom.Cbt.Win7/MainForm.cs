using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Net;
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

            Text = "SchoolDom Admin Sync Win7 v" + Application.ProductVersion;
            Width = 1280;
            Height = 760;
            MinimumSize = new Size(1120, 680);
            StartPosition = FormStartPosition.CenterScreen;
            BackColor = Palette.Background;
            Font = new Font("Segoe UI", 10);
            AutoScaleMode = AutoScaleMode.Font;
            Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath);

            _root = new Panel { Dock = DockStyle.Fill };
            Controls.Add(_root);
            if (string.IsNullOrWhiteSpace(_store.State.AccessToken)) ShowCloudLogin();
            else ShowDashboard();
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
                Text = "Sign in once to save this computer for SchoolDom sync. Use Sync Now whenever you need the latest published exams, students, and package metadata.",
                Left = 40,
                Top = 210,
                Width = 340,
                Height = 110,
                ForeColor = Palette.SoftText,
                Font = new Font("Segoe UI", 10, FontStyle.Regular)
            });

            var content = new Panel { Dock = DockStyle.Fill, BackColor = Palette.Background };
            var card = Card(82, 64, 590, 500);
            content.Controls.Add(card);

            card.Controls.Add(TextLabel("Cloud Login", 34, 28, 20, true, 480, Palette.Text));
            card.Controls.Add(TextLabel("Use an admin, principal, super admin, teacher, or accountant account with CBT sync permission.", 36, 76, 10, false, 500, Palette.Muted));

            var url = Field(card, "Cloud URL", _store.State.CloudUrl ?? "https://schooldom.academy", 36, 148, false);
            url.Width = 500;
            var email = Field(card, "Email", "", 36, 228, false);
            var password = Field(card, "Password", "", 306, 228, true);
            var schoolCode = Field(card, "School Code", "", 36, 308, false);

            _statusLabel = TextLabel("", 36, 438, 10, false, 500, Palette.Muted);
            card.Controls.Add(_statusLabel);

            var login = PrimaryButton("Login and Sync", 36, 382, 180);
            login.Click += (s, e) =>
            {
                RunWithStatus("Signing in and pulling school data...", () =>
                {
                    _cloud.Login(url.Text, email.Text, password.Text, schoolCode.Text);
                    return _cloud.PullPackage("");
                }, ShowDashboard);
            };
            card.Controls.Add(login);

            var token = SecondaryButton("Use JWT Token", 210, 382, 166);
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

            var import = SideButton("Import Exam", 24, 294);
            import.Click += ImportPackage;
            sidebar.Controls.Add(import);

            var export = SideButton("Export Results", 24, 348);
            export.Click += ExportResults;
            sidebar.Controls.Add(export);

            var results = SideButton("Manage Results", 24, 402);
            results.Click += (s, e) => ShowResultList();
            sidebar.Controls.Add(results);

            var createExam = SideButton("Create Exam", 24, 456);
            createExam.Click += (s, e) => ShowCreateExam();
            sidebar.Controls.Add(createExam);

            var installStudent = SideButton("Install Student App", 24, 510);
            installStudent.Click += InstallStudentApp;
            sidebar.Controls.Add(installStudent);

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

            var discoveryToken = _store.State.DiscoveryToken ?? "(start LAN server to generate)";
            var status = TextLabel("Cloud: " + (_store.State.CloudUrl ?? "") + "\r\nLast sync: " + Display(_store.State.LastSyncAt) + "\r\nNetwork Token: " + discoveryToken, 650, 18, 9, false, 330, Palette.Muted);
            content.Controls.Add(status);

            if (_store.State.HasPendingUpload)
            {
                var warningBanner = new Panel { Left = 34, Top = 88, Width = 940, Height = 36, BackColor = Color.FromArgb(255, 243, 205) };
                warningBanner.Anchor = AnchorStyles.Top | AnchorStyles.Left;
                var warningText = new Label
                {
                    Text = "Results pending upload. Click Upload Results to send them to the cloud.",
                    Left = 12,
                    Top = 8,
                    Width = 780,
                    Height = 20,
                    ForeColor = Color.FromArgb(133, 77, 14),
                    Font = new Font("Segoe UI", 9, FontStyle.Bold),
                    AutoSize = false
                };
                warningBanner.Controls.Add(warningText);
                var retryBtn = new Button
                {
                    Text = "Upload Now",
                    Left = 800,
                    Top = 6,
                    Width = 110,
                    Height = 24,
                    FlatStyle = FlatStyle.Flat,
                    BackColor = Color.FromArgb(184, 127, 33),
                    ForeColor = Color.White,
                    Font = new Font("Segoe UI", 8, FontStyle.Bold)
                };
                retryBtn.Click += (s, e) => RunWithStatus("Uploading pending results...", () => _cloud.RetryPendingUpload(), ShowDashboard);
                warningBanner.Controls.Add(retryBtn);
                content.Controls.Add(warningBanner);
            }

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

            var submittedResults = Card(34, 432, 1024, 230);
            submittedResults.Controls.Add(TextLabel("Submitted Results", 22, 14, 16, true, 300, Palette.Text));
            FillSubmittedResults(submittedResults);
            content.Controls.Add(submittedResults);

            var exams = Card(34, 686, 500, 410);
            exams.Controls.Add(TextLabel("Exams", 22, 18, 16, true, 240, Palette.Text));
            var moreExams = MiniButton("More", 408, 18, 74);
            moreExams.Click += (s, e) => ShowExamList();
            exams.Controls.Add(moreExams);
            FillExamList(exams);
            content.Controls.Add(exams);

            var students = Card(558, 686, 500, 410);
            students.Controls.Add(TextLabel("Students", 22, 18, 16, true, 240, Palette.Text));
            var moreStudents = MiniButton("More", 408, 18, 74);
            moreStudents.Click += (s, e) => ShowStudentList();
            students.Controls.Add(moreStudents);
            FillStudentList(students);
            content.Controls.Add(students);

            var note = Card(34, 1120, 1024, 96);
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
                var pin = MiniButton("New PIN", 244, y, 76);
                pin.Click += (s, e) => GenerateExamPin(exam);
                card.Controls.Add(pin);
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

        private void FillSubmittedResults(Panel card)
        {
            var submitted = _store.State.Sessions
                .Where(s => string.Equals(s.Status, "submitted", StringComparison.OrdinalIgnoreCase))
                .OrderByDescending(s => s.SubmittedAt ?? s.StartedAt)
                .ToList();
            var list = new ListView
            {
                Left = 22,
                Top = 54,
                Width = 790,
                Height = 150,
                View = View.Details,
                FullRowSelect = true,
                HideSelection = false
            };
            list.Columns.Add("Student", 190);
            list.Columns.Add("Student ID", 100);
            list.Columns.Add("Exam", 200);
            list.Columns.Add("Score", 110);
            list.Columns.Add("Submitted", 140);
            foreach (var session in submitted)
            {
                var student = _store.State.Students.FirstOrDefault(s => string.Equals(s.StudentId, session.StudentId, StringComparison.OrdinalIgnoreCase));
                var exam = _store.State.Exams.FirstOrDefault(e => e.Id == session.ExamId);
                var item = new ListViewItem(DisplayStudentName(session, student));
                item.SubItems.Add(session.StudentId ?? "");
                item.SubItems.Add(exam == null ? session.ExamId : exam.Title);
                item.SubItems.Add(PackageService.ComputeScore(session, exam).Display);
                item.SubItems.Add(Display(session.SubmittedAt ?? session.StartedAt));
                item.Tag = session;
                list.Items.Add(item);
            }
            card.Controls.Add(list);
            if (!submitted.Any())
            {
                card.Controls.Add(TextLabel("No results submitted yet — students must complete and submit their exams via the LAN server.", 22, 100, 9, false, 760, Palette.Muted));
            }

            var delete = PrimaryButton("Delete / Retake", 836, 70, 150);
            delete.Enabled = submitted.Any();
            delete.Click += (s, e) =>
            {
                if (list.SelectedItems.Count == 0)
                {
                    MessageBox.Show("Select a submitted result first.", "Delete Result");
                    return;
                }
                DeleteResult((SessionRecord)list.SelectedItems[0].Tag);
            };
            card.Controls.Add(delete);

            var grade = SecondaryButton("Grade Written", 836, 124, 150);
            grade.Enabled = submitted.Any();
            grade.Click += (s, e) =>
            {
                if (list.SelectedItems.Count == 0)
                {
                    MessageBox.Show("Select a submitted result first.", "Grade Written Answers");
                    return;
                }
                ShowGradeWritten((SessionRecord)list.SelectedItems[0].Tag);
            };
            card.Controls.Add(grade);

            var more = SecondaryButton("Manage All", 836, 178, 150);
            more.Click += (s, e) => ShowResultList();
            card.Controls.Add(more);

            if (!submitted.Any())
            {
                card.Controls.Add(TextLabel("No submitted results yet. Submitted exams will appear here immediately.", 22, 84, 10, false, 500, Palette.Muted));
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
                list.Columns.Add("PIN", 90);
                foreach (var exam in _store.State.Exams.OrderBy(e => e.Title))
                {
                    var item = new ListViewItem(exam.Title);
                    item.SubItems.Add(exam.Subject ?? "");
                    item.SubItems.Add(exam.ClassName ?? "");
                    item.SubItems.Add(exam.Questions.Count.ToString());
                    item.SubItems.Add(string.IsNullOrWhiteSpace(exam.PinHash) ? "Missing" : "Ready");
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
                var generatePin = SecondaryButton("Generate PIN", 154, 458, 140);
                generatePin.Anchor = AnchorStyles.Left | AnchorStyles.Bottom;
                generatePin.Click += (s, e) =>
                {
                    if (list.SelectedItems.Count == 0) return;
                    GenerateExamPin((ExamRecord)list.SelectedItems[0].Tag);
                    form.Close();
                };
                var panel = new Panel { Dock = DockStyle.Bottom, Height = 58 };
                panel.Controls.Add(edit);
                panel.Controls.Add(generatePin);
                form.Controls.Add(list);
                form.Controls.Add(panel);
                form.ShowDialog(this);
            }
        }

        private void ShowCreateExam()
        {
            using (var form = ListForm("Create Exam", 980, 680))
            {
                var left = 104;
                var title = Field(form, "Title", "", left, 62, false);
                title.Width = 340;
                var subject = Field(form, "Subject", "", left + 364, 62, false);
                subject.Width = 180;
                var className = Field(form, "Class", "", left + 572, 62, false);
                className.Width = 170;
                var duration = Field(form, "Duration Minutes", "60", left, 132, false);
                var pin = Field(form, "LAN PIN", "", left + 250, 132, false);
                ApplyNumbersOnly(pin);
                var publish = new CheckBox { Left = left + 500, Top = 136, Width = 240, Height = 28, Text = "Create and publish on cloud", Checked = true, Font = new Font("Segoe UI", 10) };
                form.Controls.Add(publish);
                form.Controls.Add(TextLabel("Instructions", left, 182, 9, true, 220, Palette.Text));
                var instructions = new TextBox { Left = left, Top = 206, Width = 742, Height = 72, Multiline = true, ScrollBars = ScrollBars.Vertical, Font = MathFont(11) };
                form.Controls.Add(instructions);

                var questions = new List<QuestionRecord>();
                form.Controls.Add(TextLabel("Questions", left, 292, 11, true, 220, Palette.Text));
                var list = CompactQuestionList(left, 320, 742, 150);
                form.Controls.Add(list);

                Action refreshQuestions = () =>
                {
                    list.Items.Clear();
                    for (var i = 0; i < questions.Count; i++)
                    {
                        var q = questions[i];
                        var item = new ListViewItem((i + 1).ToString());
                        item.SubItems.Add(q.Text ?? "");
                        item.SubItems.Add((q.Options == null ? 0 : q.Options.Count).ToString());
                        item.SubItems.Add(q.CorrectAnswer ?? "");
                        item.Tag = q;
                        list.Items.Add(item);
                    }
                };

                var add = SecondaryButton("Add Question", left, 490, 130);
                add.Click += (s, e) =>
                {
                    var question = PromptQuestion(null);
                    if (question == null) return;
                    questions.Add(question);
                    refreshQuestions();
                };
                form.Controls.Add(add);

                var edit = SecondaryButton("Edit", left + 142, 490, 80);
                edit.Click += (s, e) =>
                {
                    if (list.SelectedItems.Count == 0) return;
                    var index = list.SelectedItems[0].Index;
                    var updated = PromptQuestion(questions[index]);
                    if (updated == null) return;
                    questions[index] = updated;
                    refreshQuestions();
                };
                form.Controls.Add(edit);

                var remove = SecondaryButton("Remove", left + 232, 490, 90);
                remove.Click += (s, e) =>
                {
                    if (list.SelectedItems.Count == 0) return;
                    questions.RemoveAt(list.SelectedItems[0].Index);
                    refreshQuestions();
                };
                form.Controls.Add(remove);

                var save = PrimaryButton("Save Exam", left + 612, 490, 130);
                save.Click += (s, e) =>
                {
                    int minutes;
                    if (title.Text.Trim().Length < 3)
                    {
                        MessageBox.Show("Enter an exam title.", "Create Exam");
                        return;
                    }
                    if (!int.TryParse(duration.Text.Trim(), out minutes) || minutes < 1)
                    {
                        MessageBox.Show("Enter a valid duration in minutes.", "Create Exam");
                        return;
                    }
                    if (questions.Count == 0)
                    {
                        MessageBox.Show("Add at least one question.", "Create Exam");
                        return;
                    }
                    if (!publish.Checked && string.IsNullOrWhiteSpace(pin.Text))
                    {
                        MessageBox.Show("Enter a LAN PIN for local-only exams.", "Create Exam");
                        return;
                    }
                    if (!string.IsNullOrWhiteSpace(pin.Text) && !IsDigitsOnly(pin.Text.Trim()))
                    {
                        MessageBox.Show("LAN PIN must contain numbers only.", "Create Exam");
                        return;
                    }

                    var started = DateTime.UtcNow;
                    var exam = new ExamRecord
                    {
                        Id = "local_exam_" + Guid.NewGuid().ToString("N"),
                        Title = title.Text.Trim(),
                        Subject = subject.Text.Trim(),
                        ClassName = className.Text.Trim(),
                        DurationSeconds = minutes * 60,
                        StartsAt = started.ToString("o"),
                        EndsAt = started.AddDays(30).ToString("o"),
                        Instructions = instructions.Text.Trim(),
                        PinHash = string.IsNullOrWhiteSpace(pin.Text) ? "" : JsonUtil.Sha256(pin.Text.Trim()),
                        Questions = questions
                    };

                    try
                    {
                        Cursor = Cursors.WaitCursor;
                        var cloudPin = "";
                        if (publish.Checked)
                        {
                            var created = _cloud.CreateExam(exam, true);
                            var cloudExam = created.ContainsKey("exam") ? created["exam"] as Dictionary<string, object> : null;
                            var cloudExamId = cloudExam == null ? "" : JsonUtil.Text(cloudExam.ContainsKey("id") ? cloudExam["id"] : "");
                            if (!string.IsNullOrWhiteSpace(cloudExamId)) exam.Id = cloudExamId;
                            var pinData = _cloud.RegenerateExamPin(exam.Id);
                            cloudPin = JsonUtil.Text(pinData.ContainsKey("pin") ? pinData["pin"] : "");
                            var pinHash = JsonUtil.Text(pinData.ContainsKey("offline_pin_hash") ? pinData["offline_pin_hash"] : "");
                            if (!string.IsNullOrWhiteSpace(pinHash)) exam.PinHash = pinHash;
                        }
                        else if (string.IsNullOrWhiteSpace(exam.PinHash))
                        {
                            throw new InvalidOperationException("Enter a LAN PIN before saving this exam.");
                        }

                        _packages.AddExam(exam);
                        Cursor = Cursors.Default;
                        var message = "Exam saved and ready for LAN CBT.";
                        if (!string.IsNullOrWhiteSpace(cloudPin)) message += "\r\n\r\nCloud PIN: " + cloudPin;
                        else if (!string.IsNullOrWhiteSpace(pin.Text)) message += "\r\n\r\nLAN PIN: " + pin.Text.Trim();
                        MessageBox.Show(message, "Exam Created");
                        form.Close();
                        ShowDashboard();
                    }
                    catch (CloudAuthExpiredException ex)
                    {
                        Cursor = Cursors.Default;
                        form.Close();
                        HandleCloudAuthExpired(ex);
                    }
                    catch (Exception ex)
                    {
                        Cursor = Cursors.Default;
                        MessageBox.Show(ex.Message, "Create Exam Failed");
                    }
                };
                form.Controls.Add(save);
                form.ShowDialog(this);
            }
        }

        private QuestionRecord PromptQuestion(QuestionRecord existing)
        {
            using (var form = ListForm(existing == null ? "Add Question" : "Edit Question", 620, 520))
            {
                var existingOptions = existing == null || existing.Options == null ? new List<string>() : existing.Options;
                form.Controls.Add(TextLabel("Question", 28, 24, 9, true, 220, Palette.Text));
                var text = new TextBox { Left = 28, Top = 48, Width = 540, Height = 78, Multiline = true, ScrollBars = ScrollBars.Vertical, Text = existing == null ? "" : existing.Text ?? "", Font = MathFont(11) };
                form.Controls.Add(text);
                var optionA = Field(form, "Option A", existingOptions.Count > 0 ? existingOptions[0] : "", 28, 172, false);
                optionA.Width = 250;
                optionA.Font = MathFont(11);
                var optionB = Field(form, "Option B", existingOptions.Count > 1 ? existingOptions[1] : "", 318, 172, false);
                optionB.Width = 250;
                optionB.Font = MathFont(11);
                var optionC = Field(form, "Option C", existingOptions.Count > 2 ? existingOptions[2] : "", 28, 248, false);
                optionC.Width = 250;
                optionC.Font = MathFont(11);
                var optionD = Field(form, "Option D", existingOptions.Count > 3 ? existingOptions[3] : "", 318, 248, false);
                optionD.Width = 250;
                optionD.Font = MathFont(11);
                form.Controls.Add(TextLabel("Correct Answer", 28, 310, 9, true, 220, Palette.Text));
                var correct = new ComboBox { Left = 28, Top = 334, Width = 250, Height = 32, DropDownStyle = ComboBoxStyle.DropDownList };
                correct.Items.AddRange(new object[] { "A", "B", "C", "D" });
                correct.SelectedIndex = 0;
                if (existing != null)
                {
                    var index = existingOptions.FindIndex(o => string.Equals(o, existing.CorrectAnswer, StringComparison.OrdinalIgnoreCase));
                    if (index >= 0 && index < correct.Items.Count) correct.SelectedIndex = index;
                }
                form.Controls.Add(correct);
                var marks = Field(form, "Marks", existing == null ? "1" : Math.Max(1, existing.Points).ToString(), 318, 334, false);
                marks.Width = 90;

                QuestionRecord result = null;
                var save = PrimaryButton("Save Question", 28, 420, 140);
                save.Click += (s, e) =>
                {
                    var options = new List<string>();
                    foreach (var box in new[] { optionA, optionB, optionC, optionD })
                    {
                        if (!string.IsNullOrWhiteSpace(box.Text)) options.Add(box.Text.Trim());
                    }
                    double pointValue;
                    if (text.Text.Trim().Length < 3)
                    {
                        MessageBox.Show("Enter the question text.", "Question");
                        return;
                    }
                    if (options.Count < 2)
                    {
                        MessageBox.Show("Enter at least two options.", "Question");
                        return;
                    }
                    if (!double.TryParse(marks.Text.Trim(), out pointValue) || pointValue <= 0) pointValue = 1;
                    var selected = correct.SelectedIndex;
                    if (selected >= options.Count) selected = 0;
                    result = new QuestionRecord
                    {
                        Id = existing == null || string.IsNullOrWhiteSpace(existing.Id) ? "local_question_" + Guid.NewGuid().ToString("N") : existing.Id,
                        Text = text.Text.Trim(),
                        Type = "mcq",
                        Points = pointValue,
                        Options = options,
                        CorrectAnswer = options[selected]
                    };
                    form.Close();
                };
                form.Controls.Add(save);
                form.ShowDialog(this);
                return result;
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

        private void ShowResultList()
        {
            using (var form = ListForm("Submitted Results", 900, 560))
            {
                var list = new ListView { Dock = DockStyle.Fill, View = View.Details, FullRowSelect = true };
                list.Columns.Add("Student", 220);
                list.Columns.Add("Student ID", 120);
                list.Columns.Add("Exam", 220);
                list.Columns.Add("Status", 90);
                list.Columns.Add("Score", 110);
                list.Columns.Add("Submitted", 150);
                foreach (var session in _store.State.Sessions.Where(s => string.Equals(s.Status, "submitted", StringComparison.OrdinalIgnoreCase)).OrderByDescending(s => s.SubmittedAt ?? s.StartedAt))
                {
                    var student = _store.State.Students.FirstOrDefault(s => string.Equals(s.StudentId, session.StudentId, StringComparison.OrdinalIgnoreCase));
                    var exam = _store.State.Exams.FirstOrDefault(e => e.Id == session.ExamId);
                    var item = new ListViewItem(DisplayStudentName(session, student));
                    item.SubItems.Add(session.StudentId ?? "");
                    item.SubItems.Add(exam == null ? session.ExamId : exam.Title);
                    item.SubItems.Add(session.Status ?? "");
                    item.SubItems.Add(PackageService.ComputeScore(session, exam).Display);
                    item.SubItems.Add(Display(session.SubmittedAt ?? session.StartedAt));
                    item.Tag = session;
                    list.Items.Add(item);
                }
                var delete = PrimaryButton("Delete / Allow Retake", 12, 8, 180);
                delete.Click += (s, e) =>
                {
                    if (list.SelectedItems.Count == 0) return;
                    DeleteResult((SessionRecord)list.SelectedItems[0].Tag);
                    form.Close();
                };
                var gradeWritten = SecondaryButton("Grade Written", 204, 8, 160);
                gradeWritten.Click += (s, e) =>
                {
                    if (list.SelectedItems.Count == 0) return;
                    ShowGradeWritten((SessionRecord)list.SelectedItems[0].Tag);
                    form.Close();
                };
                var panel = new Panel { Dock = DockStyle.Bottom, Height = 58 };
                panel.Controls.Add(delete);
                panel.Controls.Add(gradeWritten);
                form.Controls.Add(list);
                form.Controls.Add(panel);
                form.ShowDialog(this);
            }
        }

        private void ShowGradeWritten(SessionRecord session)
        {
            if (session == null) return;
            var exam = _store.State.Exams.FirstOrDefault(e => e.Id == session.ExamId);
            if (exam == null)
            {
                MessageBox.Show("This exam is no longer available locally.", "Grade Written Answers");
                return;
            }
            var written = (exam.Questions ?? new List<QuestionRecord>()).Where(q => PackageService.IsWrittenType(q.Type)).ToList();
            if (written.Count == 0)
            {
                MessageBox.Show("This exam has no written/essay questions to grade. Objective questions are scored automatically.", "Grade Written Answers");
                return;
            }

            using (var form = ListForm("Grade Written Answers: " + exam.Title, 860, 640))
            {
                var scroll = new Panel { Dock = DockStyle.Fill, AutoScroll = true };
                var marksBoxes = new List<NumericUpDown>();
                var y = 16;
                for (var i = 0; i < written.Count; i++)
                {
                    var q = written[i];
                    var maxPoints = q.Points <= 0 ? 1 : q.Points;
                    object rawAnswer;
                    var answerText = session.Answers != null && session.Answers.TryGetValue(q.Id, out rawAnswer)
                        ? JsonUtil.Text(rawAnswer)
                        : "";
                    if (string.IsNullOrWhiteSpace(answerText)) answerText = "(No answer submitted)";

                    scroll.Controls.Add(TextLabel((i + 1) + ". " + q.Text + "  (max " + PackageService.FormatScoreNumber(maxPoints) + ")", 16, y, 10, true, 760, Palette.Text));
                    y += 28;
                    var answerBox = new TextBox
                    {
                        Left = 16,
                        Top = y,
                        Width = 700,
                        Height = 70,
                        Multiline = true,
                        ReadOnly = true,
                        ScrollBars = ScrollBars.Vertical,
                        Text = answerText,
                        Font = MathFont(10)
                    };
                    scroll.Controls.Add(answerBox);
                    y += 80;

                    scroll.Controls.Add(TextLabel("Marks awarded", 16, y + 4, 9, false, 120, Palette.Muted));
                    double existing;
                    var marks = new NumericUpDown
                    {
                        Left = 140,
                        Top = y,
                        Width = 90,
                        Minimum = 0,
                        Maximum = (decimal)maxPoints,
                        DecimalPlaces = 2,
                        Increment = 0.5m,
                        Value = session.ManualScores != null && session.ManualScores.TryGetValue(q.Id, out existing)
                            ? Math.Min((decimal)existing, (decimal)maxPoints)
                            : 0
                    };
                    marks.Tag = q.Id;
                    scroll.Controls.Add(marks);
                    marksBoxes.Add(marks);
                    y += 50;
                }

                var actions = new Panel { Dock = DockStyle.Bottom, Height = 58 };
                var save = PrimaryButton("Save Grades", 12, 8, 150);
                save.Click += (s, e) =>
                {
                    if (session.ManualScores == null) session.ManualScores = new Dictionary<string, double>();
                    foreach (var box in marksBoxes)
                    {
                        session.ManualScores[(string)box.Tag] = (double)box.Value;
                    }
                    _store.Save();
                    form.Close();
                    ShowDashboard();
                };
                actions.Controls.Add(save);

                form.Controls.Add(scroll);
                form.Controls.Add(actions);
                form.ShowDialog(this);
            }
        }

        private void ShowExamReview(ExamRecord exam)
        {
            using (var form = ListForm("Review: " + exam.Title, 860, 620))
            {
                var actions = new Panel { Dock = DockStyle.Bottom, Height = 58, BackColor = Palette.Background };
                var edit = PrimaryButton("Edit Exam", 12, 8, 120);
                edit.Click += (s, e) =>
                {
                    form.Close();
                    ShowExamEditor(exam);
                };
                actions.Controls.Add(edit);

                var text = new TextBox
                {
                    Dock = DockStyle.Fill,
                    Multiline = true,
                    ReadOnly = true,
                    ScrollBars = ScrollBars.Vertical,
                    Font = MathFont(10),
                    Text = BuildExamReviewText(exam)
                };
                form.Controls.Add(text);
                form.Controls.Add(actions);
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
                var options = q.Options ?? new System.Collections.Generic.List<string>();
                for (var j = 0; j < options.Count; j++)
                {
                    lines.AppendLine("   " + (char)('A' + j) + ". " + options[j]);
                }
                lines.AppendLine();
            }
            return lines.ToString();
        }

        private void ShowExamEditor(ExamRecord exam)
        {
            using (var form = ListForm("Edit Exam", 880, 660))
            {
                var left = 54;
                var title = Field(form, "Title", exam.Title, left, 62, false);
                title.Width = 360;
                var subject = Field(form, "Subject", exam.Subject, left + 390, 62, false);
                subject.Width = 180;
                var className = Field(form, "Class", exam.ClassName, left + 590, 62, false);
                className.Width = 190;
                var duration = Field(form, "Duration Minutes", Math.Max(1, exam.DurationSeconds / 60).ToString(), left, 132, false);
                var instructionsLabel = TextLabel("Instructions", left, 182, 9, true, 220, Palette.Text);
                form.Controls.Add(instructionsLabel);
                var instructions = new TextBox
                {
                    Left = left,
                    Top = 206,
                    Width = 742,
                    Height = 72,
                    Multiline = true,
                    ScrollBars = ScrollBars.Vertical,
                    Text = exam.Instructions ?? "",
                    Font = MathFont(11)
                };
                form.Controls.Add(instructions);
                var questions = (exam.Questions ?? new List<QuestionRecord>()).ToList();
                form.Controls.Add(TextLabel("Questions", left, 292, 11, true, 220, Palette.Text));
                var list = CompactQuestionList(left, 320, 742, 150);
                Action refreshQuestions = () =>
                {
                    list.Items.Clear();
                    for (var i = 0; i < questions.Count; i++)
                    {
                        var q = questions[i];
                        var item = new ListViewItem((i + 1).ToString());
                        item.SubItems.Add(q.Text ?? "");
                        item.SubItems.Add((q.Options == null ? 0 : q.Options.Count).ToString());
                        item.SubItems.Add(q.CorrectAnswer ?? "");
                        item.Tag = q;
                        list.Items.Add(item);
                    }
                };
                refreshQuestions();
                form.Controls.Add(list);
                var add = SecondaryButton("Add Question", left, 490, 130);
                add.Click += (s, e) => { var q = PromptQuestion(null); if (q != null) { questions.Add(q); refreshQuestions(); } };
                form.Controls.Add(add);
                var edit = SecondaryButton("Edit", left + 142, 490, 80);
                edit.Click += (s, e) =>
                {
                    if (list.SelectedItems.Count == 0) return;
                    var index = list.SelectedItems[0].Index;
                    var q = PromptQuestion(questions[index]);
                    if (q != null) { questions[index] = q; refreshQuestions(); }
                };
                form.Controls.Add(edit);
                var remove = SecondaryButton("Remove", left + 232, 490, 90);
                remove.Click += (s, e) => { if (list.SelectedItems.Count > 0) { questions.RemoveAt(list.SelectedItems[0].Index); refreshQuestions(); } };
                form.Controls.Add(remove);
                var save = PrimaryButton("Save Changes", left + 602, 490, 140);
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
                    exam.Questions = questions;
                    _packages.SaveExam(exam);
                    form.Close();
                    ShowDashboard();
                };
                form.Controls.Add(save);
                form.ShowDialog(this);
            }
        }

        private void GenerateExamPin(ExamRecord exam)
        {
            if (exam == null) return;
            if (MessageBox.Show("Generate a new PIN for " + exam.Title + "?\r\n\r\nThe old PIN will stop working on the website and on this LAN after the update.", "Generate New PIN", MessageBoxButtons.YesNo, MessageBoxIcon.Question) != DialogResult.Yes) return;
            try
            {
                Cursor = Cursors.WaitCursor;
                var data = _cloud.RegenerateExamPin(exam.Id);
                var pin = JsonUtil.Text(data.ContainsKey("pin") ? data["pin"] : "");
                var pinHash = JsonUtil.Text(data.ContainsKey("offline_pin_hash") ? data["offline_pin_hash"] : "");
                if (string.IsNullOrWhiteSpace(pin) || string.IsNullOrWhiteSpace(pinHash))
                {
                    throw new InvalidOperationException("The website generated a PIN but did not return the offline PIN hash.");
                }
                exam.PinHash = pinHash;
                _packages.SaveExam(exam);
                Cursor = Cursors.Default;
                MessageBox.Show("New PIN for " + exam.Title + ":\r\n\r\n" + pin + "\r\n\r\nGive this PIN to students for the LAN CBT app.", "New Exam PIN");
                ShowDashboard();
            }
            catch (CloudAuthExpiredException ex)
            {
                Cursor = Cursors.Default;
                HandleCloudAuthExpired(ex);
            }
            catch (Exception ex)
            {
                Cursor = Cursors.Default;
                MessageBox.Show(ex.Message, "PIN Generation Failed");
            }
        }

        private void DeleteResult(SessionRecord session)
        {
            if (session == null) return;
            var exam = _store.State.Exams.FirstOrDefault(e => e.Id == session.ExamId);
            var title = exam == null ? session.ExamId : exam.Title;
            if (MessageBox.Show("Delete this result and allow the student to retake?\r\n\r\n" + session.StudentId + "\r\n" + title, "Delete Result", MessageBoxButtons.YesNo, MessageBoxIcon.Warning) != DialogResult.Yes) return;
            try
            {
                Cursor = Cursors.WaitCursor;
                try
                {
                    _cloud.DeleteResult(session.ExamId, session.StudentId, session.Id);
                }
                catch (CloudAuthExpiredException ex)
                {
                    Cursor = Cursors.Default;
                    HandleCloudAuthExpired(ex);
                    return;
                }
                catch (Exception ex)
                {
                    if (MessageBox.Show("Cloud delete failed:\r\n\r\n" + ex.Message + "\r\n\r\nRemove the local result anyway?", "Cloud Delete Failed", MessageBoxButtons.YesNo, MessageBoxIcon.Warning) != DialogResult.Yes)
                    {
                        Cursor = Cursors.Default;
                        return;
                    }
                }
                var message = _packages.DeleteSession(session.Id);
                Cursor = Cursors.Default;
                MessageBox.Show(message, "Result Deleted");
                ShowDashboard();
            }
            catch (Exception ex)
            {
                Cursor = Cursors.Default;
                MessageBox.Show(ex.Message, "Delete Result Failed");
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
            catch (CloudAuthExpiredException ex)
            {
                Cursor = Cursors.Default;
                HandleCloudAuthExpired(ex);
            }
            catch (Exception ex)
            {
                Cursor = Cursors.Default;
                SetStatus(ex.Message, Palette.Coral);
                MessageBox.Show(ex.Message, "SchoolDom Sync Failed");
            }
        }

        private void HandleCloudAuthExpired(CloudAuthExpiredException ex)
        {
            _store.State.AccessToken = "";
            _store.Save();
            SetStatus(ex.Message, Palette.Coral);
            MessageBox.Show(ex.Message, "Cloud Login Expired");
            ShowCloudLogin();
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
                dialog.Filter = "Exam files (*.json;*.csv;*.txt;*.docx)|*.json;*.csv;*.txt;*.docx|JSON (*.json)|*.json|CSV (*.csv)|*.csv|Text (*.txt)|*.txt|Word document (*.docx)|*.docx|All files (*.*)|*.*";
                if (dialog.ShowDialog(this) != DialogResult.OK) return;
                try
                {
                    var fallbackPin = PromptDialog.Show("LAN PIN", "Optional: enter a numeric LAN PIN for this imported exam if the file does not include one.", true, true);
                    MessageBox.Show(_packages.ImportExamFile(dialog.FileName, fallbackPin), "Import Exam");
                    ShowDashboard();
                }
                catch (Exception ex)
                {
                    MessageBox.Show(ex.Message, "Import Exam Failed");
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

        private void InstallStudentApp(object sender, EventArgs e)
        {
            try
            {
                Cursor = Cursors.WaitCursor;
                var bundledPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "SchoolDomStudentCBT-Win7.exe");
                var targetPath = bundledPath;
                if (!IsValidInstaller(targetPath))
                {
                    var cloudUrl = _cloud.NormalizeCloudUrl(_store.State.CloudUrl);
                    var downloadUrl = cloudUrl + "/app/download/student-cbt/win7/student/";
                    var targetDir = Path.Combine(Path.GetTempPath(), "SchoolDom");
                    Directory.CreateDirectory(targetDir);
                    targetPath = Path.Combine(targetDir, "SchoolDomStudentCBT-Win7.exe");
                    using (var client = new WebClient())
                    {
                        client.Headers["User-Agent"] = "SchoolDom-Admin-Sync-Win7";
                        client.DownloadFile(downloadUrl, targetPath);
                    }
                    if (!IsValidInstaller(targetPath))
                    {
                        throw new InvalidOperationException("The downloaded student installer is not a valid Windows setup file. Rebuild or upload SchoolDomStudentCBT-Win7.exe on the website.");
                    }
                }
                Cursor = Cursors.Default;
                Process.Start(targetPath);
                MessageBox.Show("Student CBT installer downloaded and started.", "Student App");
            }
            catch (Exception ex)
            {
                Cursor = Cursors.Default;
                MessageBox.Show(ex.Message, "Student App Installer Failed");
            }
        }

        private static bool IsValidInstaller(string path)
        {
            if (string.IsNullOrWhiteSpace(path) || !File.Exists(path)) return false;
            var info = new FileInfo(path);
            if (info.Length < 512 * 1024) return false;
            using (var stream = File.OpenRead(path))
            {
                if (stream.Length < 2) return false;
                return stream.ReadByte() == 'M' && stream.ReadByte() == 'Z';
            }
        }

        private TextBox Field(Control parent, string label, string value, int left, int top, bool password)
        {
            var labelControl = new Label
            {
                Text = label,
                Left = left,
                Top = top - 30,
                AutoSize = true,
                Font = new Font("Segoe UI", 9, FontStyle.Bold),
                ForeColor = Palette.Text,
                UseCompatibleTextRendering = true
            };
            parent.Controls.Add(labelControl);
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

        private ListView CompactQuestionList(int left, int top, int width, int height)
        {
            var list = new ListView
            {
                Left = left,
                Top = top,
                Width = width,
                Height = height,
                View = View.Details,
                FullRowSelect = true,
                GridLines = true,
                HideSelection = false,
                Font = new Font("Segoe UI", 9),
                SmallImageList = new ImageList { ImageSize = new Size(1, 18) }
            };
            list.Columns.Add("#", 36);
            list.Columns.Add("Question", 420);
            list.Columns.Add("Options", 70);
            list.Columns.Add("Correct", 190);
            return list;
        }

        private void ApplyNumbersOnly(TextBox box)
        {
            box.KeyPress += (sender, args) =>
            {
                if (!char.IsControl(args.KeyChar) && !char.IsDigit(args.KeyChar)) args.Handled = true;
            };
            box.TextChanged += (sender, args) =>
            {
                var clean = OnlyDigits(box.Text);
                if (clean == box.Text) return;
                var selectionStart = box.SelectionStart;
                box.Text = clean;
                box.SelectionStart = selectionStart > box.Text.Length ? box.Text.Length : selectionStart;
            };
        }

        private static bool IsDigitsOnly(string value)
        {
            if (string.IsNullOrWhiteSpace(value)) return false;
            foreach (char c in value)
            {
                if (!char.IsDigit(c)) return false;
            }
            return true;
        }

        private static string OnlyDigits(string value)
        {
            var clean = "";
            foreach (char c in value ?? "")
            {
                if (char.IsDigit(c)) clean += c;
            }
            return clean;
        }

        private Panel Metric(string label, string value, int left, int top, Color accent)
        {
            var card = Card(left, top, 224, 96);
            var bar = new Panel { Left = 0, Top = 0, Width = 5, Height = 96, BackColor = accent };
            card.Controls.Add(bar);
            card.Controls.Add(TextLabel(label, 20, 14, 9, true, 180, Palette.Muted));
            card.Controls.Add(TextLabel(value, 20, 44, 18, true, 180, Palette.Text));
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
            return new Label
            {
                Text = text,
                Left = left,
                Top = top,
                AutoSize = true,
                MaximumSize = new Size(width, 0),
                Font = new Font("Segoe UI", size, bold ? FontStyle.Bold : FontStyle.Regular),
                ForeColor = color,
                UseCompatibleTextRendering = true
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

        private Font MathFont(float size)
        {
            try { return new Font("Cambria Math", size, FontStyle.Regular); }
            catch { return new Font("Segoe UI Symbol", size, FontStyle.Regular); }
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

        private string DisplayStudentName(SessionRecord session, StudentRecord student)
        {
            var studentId = session == null ? "" : session.StudentId;
            var name = session == null ? "" : session.StudentName;
            if (LooksLikeStudentId(name, studentId)) name = "";
            if (string.IsNullOrWhiteSpace(name) && student != null) name = student.FullName;
            if (LooksLikeStudentId(name, studentId)) name = "";
            return string.IsNullOrWhiteSpace(name) ? (studentId ?? "") : name.Trim();
        }

        private static bool LooksLikeStudentId(string value, string studentId)
        {
            return !string.IsNullOrWhiteSpace(value) && string.Equals(value.Trim(), (studentId ?? "").Trim(), StringComparison.OrdinalIgnoreCase);
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
