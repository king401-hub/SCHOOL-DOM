using System;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;
using System.Windows.Forms;
using SchoolDom.Rfid.Win7.Controls;

namespace SchoolDom.Rfid.Win7
{
    // Section 4c - select a class, then a repeating scan queue: each scan defaults
    // to the next unassigned student in that class (editable via dropdown), and
    // confirming immediately advances to the next one without leaving the screen.
    internal sealed class BulkAssignForm : Form
    {
        private readonly ReaderManager _readerManager;
        private readonly SyncService _sync;

        private ComboBox _classPicker;
        private Label _progressLabel;
        private Card _scanCard;
        private Label _capturedUidLabel;
        private ComboBox _studentPicker;
        private RoundedButton _confirmButton;
        private ListBox _sessionLog;

        private List<PersonOption> _unassignedInClass = new List<PersonOption>();
        private int _totalInClass;
        private string _capturedUid;

        public BulkAssignForm(ReaderManager readerManager, SyncService sync)
        {
            _readerManager = readerManager;
            _sync = sync;

            Text = "Bulk Assign Cards";
            Width = 820;
            Height = 620;
            StartPosition = FormStartPosition.CenterParent;
            BackColor = Palette.Background;
            Font = Palette.Body;
            MinimumSize = new Size(760, 560);

            BuildLayout();

            Load += (s, e) =>
            {
                _readerManager.AssignmentModeActive = true;
                _readerManager.CardScanned += OnScan;
                LoadClasses();
            };
            FormClosed += (s, e) =>
            {
                _readerManager.AssignmentModeActive = false;
                _readerManager.CardScanned -= OnScan;
            };
        }

        private void BuildLayout()
        {
            var header = new Label { Text = "1. Select a class", Left = 20, Top = 20, AutoSize = true, Font = Palette.BodyBold, ForeColor = Palette.Text };
            Controls.Add(header);

            _classPicker = new ComboBox { Left = 20, Top = 46, Width = 380, Height = 34, Font = new Font("Segoe UI", 11), DropDownStyle = ComboBoxStyle.DropDownList };
            _classPicker.SelectedIndexChanged += OnClassSelected;
            Controls.Add(_classPicker);

            _progressLabel = new Label { Left = 420, Top = 50, Width = 360, AutoSize = true, Font = Palette.Body, ForeColor = Palette.Muted };
            Controls.Add(_progressLabel);

            var scanHeader = new Label { Text = "2. Scan each card", Left = 20, Top = 96, AutoSize = true, Font = Palette.BodyBold, ForeColor = Palette.Text };
            Controls.Add(scanHeader);

            _scanCard = new Card { Left = 20, Top = 124, Width = 760, Height = 160, Enabled = false, Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right };
            Controls.Add(_scanCard);

            _scanCard.Controls.Add(new Label { Text = "Card UID", Left = 20, Top = 16, AutoSize = true, Font = Palette.Caption, ForeColor = Palette.Muted });
            _capturedUidLabel = new Label
            {
                Text = "Waiting for a scan...",
                Left = 20, Top = 36, Width = 340, Height = 40,
                Font = new Font("Consolas", 16, FontStyle.Bold), ForeColor = Palette.Text
            };
            _scanCard.Controls.Add(_capturedUidLabel);

            _scanCard.Controls.Add(new Label { Text = "Assign to", Left = 380, Top = 16, AutoSize = true, Font = Palette.Caption, ForeColor = Palette.Muted });
            _studentPicker = new ComboBox { Left = 380, Top = 36, Width = 340, Height = 34, Font = new Font("Segoe UI", 10), DropDownStyle = ComboBoxStyle.DropDownList };
            _scanCard.Controls.Add(_studentPicker);

            _confirmButton = RoundedButton.Primary("Confirm & Next", 340, 44);
            _confirmButton.Left = 380;
            _confirmButton.Top = 96;
            _confirmButton.Enabled = false;
            _confirmButton.Click += OnConfirmClick;
            _scanCard.Controls.Add(_confirmButton);

            var logHeader = new Label { Text = "This session", Left = 20, Top = 300, AutoSize = true, Font = Palette.BodyBold, ForeColor = Palette.Text };
            Controls.Add(logHeader);

            _sessionLog = new ListBox
            {
                Left = 20, Top = 328, Width = 760, Height = 220,
                Font = Palette.Body, BorderStyle = BorderStyle.FixedSingle,
                Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Bottom
            };
            Controls.Add(_sessionLog);
        }

        private void LoadClasses()
        {
            Cursor = Cursors.WaitCursor;
            try
            {
                var classes = _sync.PullClasses();
                _classPicker.DataSource = classes;
                _classPicker.DisplayMember = "Label";
            }
            catch (CloudAuthExpiredException)
            {
                MessageBox.Show(this, "Your sign-in has expired. Close this window and sign in again.", "Sign-in Expired", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            }
            catch (Exception ex)
            {
                MessageBox.Show(this, ex.Message, "Could Not Load Classes", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            }
            finally
            {
                Cursor = Cursors.Default;
            }
        }

        private void OnClassSelected(object sender, EventArgs e)
        {
            var selected = _classPicker.SelectedItem as ClassOption;
            if (selected == null) return;

            Cursor = Cursors.WaitCursor;
            try
            {
                // Bulk Assign is deliberately student-only ("class" isn't a concept
                // for staff) - roles="student" scopes the picker accordingly.
                var allInClass = _sync.PullPeople(selected.Id, "", "student", false);
                _totalInClass = allInClass.Count;
                _unassignedInClass = allInClass.Where(s => !s.HasActiveCard).ToList();
                RefreshProgressLabel();
                RefreshStudentPicker();
                _scanCard.Enabled = _unassignedInClass.Count > 0;
                if (_unassignedInClass.Count == 0)
                {
                    _capturedUidLabel.Text = "Every student in this class already has a card.";
                }
            }
            catch (CloudAuthExpiredException)
            {
                MessageBox.Show(this, "Your sign-in has expired. Close this window and sign in again.", "Sign-in Expired", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            }
            catch (Exception ex)
            {
                MessageBox.Show(this, ex.Message, "Could Not Load Students", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            }
            finally
            {
                Cursor = Cursors.Default;
            }
        }

        private void RefreshProgressLabel()
        {
            var remaining = _unassignedInClass.Count;
            _progressLabel.Text = (_totalInClass - remaining) + " of " + _totalInClass + " students in this class have a card.";
        }

        private void RefreshStudentPicker()
        {
            _studentPicker.DataSource = null;
            _studentPicker.DataSource = _unassignedInClass;
            _studentPicker.DisplayMember = "Name";
            if (_unassignedInClass.Count > 0) _studentPicker.SelectedIndex = 0;
        }

        private void OnScan(object sender, CardScannedEventArgs e)
        {
            if (_unassignedInClass.Count == 0) return;
            _capturedUid = e.Uid;
            _capturedUidLabel.Text = e.Uid;
            _confirmButton.Enabled = _studentPicker.SelectedItem != null;
        }

        private void OnConfirmClick(object sender, EventArgs e)
        {
            var student = _studentPicker.SelectedItem as PersonOption;
            if (student == null || string.IsNullOrEmpty(_capturedUid)) return;
            AttemptAssign(student, force: false);
        }

        private void AttemptAssign(PersonOption student, bool force)
        {
            Cursor = Cursors.WaitCursor;
            try
            {
                _sync.AssignCard(_capturedUid, student.Id, student.Name, student.Role, force);
                _sessionLog.Items.Insert(0, _capturedUid + "  ->  " + student.Name);
                _unassignedInClass.Remove(student);
                RefreshProgressLabel();
                RefreshStudentPicker();
                _capturedUid = null;
                _capturedUidLabel.Text = _unassignedInClass.Count > 0 ? "Waiting for a scan..." : "Every student in this class now has a card.";
                _confirmButton.Enabled = false;
                _scanCard.Enabled = _unassignedInClass.Count > 0;
            }
            catch (CardAssignmentConflictException ex)
            {
                Cursor = Cursors.Default;
                // Section 4d: same rich name/photo/class popup + explicit
                // Unassign-then-retry flow as the single-assign screen.
                string cardToRevoke = !string.IsNullOrEmpty(ex.ConflictingPersonName) ? _capturedUid : ex.ConflictingCardUid;
                string personName = !string.IsNullOrEmpty(ex.ConflictingPersonName) ? ex.ConflictingPersonName : student.Name;
                string roleLabel = !string.IsNullOrEmpty(ex.ConflictingPersonName) ? ex.ConflictingPersonRoleLabel : student.RoleLabel;
                string className = !string.IsNullOrEmpty(ex.ConflictingPersonName) ? ex.ConflictingPersonClassName : student.ClassName;
                string photoUrl = !string.IsNullOrEmpty(ex.ConflictingPersonName) ? ex.ConflictingPersonPhotoUrl : student.PhotoUrl;

                using (var dialog = new CardConflictDialog(_sync, cardToRevoke, personName, roleLabel, className, photoUrl))
                {
                    dialog.ShowDialog(this);
                    if (dialog.WasUnassigned) AttemptAssign(student, force: false);
                }
            }
            catch (CloudAuthExpiredException)
            {
                MessageBox.Show(this, "Your sign-in has expired. Close this window and sign in again.", "Sign-in Expired", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            }
            catch (Exception ex)
            {
                MessageBox.Show(this, ex.Message, "Could Not Assign Card", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            }
            finally
            {
                Cursor = Cursors.Default;
            }
        }
    }
}
