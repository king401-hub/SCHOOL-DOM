using System;
using System.Drawing;
using System.Linq;
using System.Windows.Forms;
using SchoolDom.Rfid.Win7.Controls;

namespace SchoolDom.Rfid.Win7
{
    // Section 4b (single-student assign) + Section 4d (reassignment/revocation).
    // Puts the reader into "listening mode" (Section 4b: "reuse the RfidReader
    // interface from Section 1 - works with either HID or SDK reader, whichever
    // is connected") by setting ReaderManager.AssignmentModeActive so MainForm's
    // normal attendance handling steps aside for scans captured here.
    internal sealed class CardAssignmentForm : Form
    {
        private readonly ReaderManager _readerManager;
        private readonly SyncService _sync;
        private readonly LocalStore _store;

        private TextBox _searchBox;
        private ListBox _studentList;
        private Label _currentCardLabel;
        private RoundedButton _unassignButton;
        private Card _scanCard;
        private Label _scanInstructionLabel;
        private Label _capturedUidLabel;
        private RoundedButton _confirmButton;

        private StudentOption _selectedStudent;
        private string _capturedUid;
        private readonly Timer _searchDebounce = new Timer { Interval = 350 };

        public CardAssignmentForm(ReaderManager readerManager, SyncService sync, LocalStore store)
        {
            _readerManager = readerManager;
            _sync = sync;
            _store = store;

            Text = "Assign RFID Card";
            Width = 760;
            Height = 560;
            StartPosition = FormStartPosition.CenterParent;
            BackColor = Palette.Background;
            Font = Palette.Body;
            MinimumSize = new Size(700, 500);

            BuildLayout();

            Load += (s, e) =>
            {
                _readerManager.AssignmentModeActive = true;
                _readerManager.CardScanned += OnScan;
                LoadStudents("");
            };
            FormClosed += (s, e) =>
            {
                _readerManager.AssignmentModeActive = false;
                _readerManager.CardScanned -= OnScan;
            };
        }

        private void BuildLayout()
        {
            var left = new Panel { Left = 20, Top = 20, Width = 340, Height = 500, BackColor = Palette.Background };
            Controls.Add(left);

            left.Controls.Add(new Label { Text = "Find a student", Left = 0, Top = 0, AutoSize = true, Font = Palette.BodyBold, ForeColor = Palette.Text });
            _searchBox = new TextBox { Left = 0, Top = 28, Width = 340, Height = 34, Font = new Font("Segoe UI", 11), BorderStyle = BorderStyle.FixedSingle };
            _searchBox.TextChanged += (s, e) => { _searchDebounce.Stop(); _searchDebounce.Start(); };
            _searchDebounce.Tick += (s, e) => { _searchDebounce.Stop(); LoadStudents(_searchBox.Text.Trim()); };
            left.Controls.Add(_searchBox);

            _studentList = new ListBox { Left = 0, Top = 70, Width = 340, Height = 430, Font = Palette.Body, BorderStyle = BorderStyle.FixedSingle, IntegralHeight = false };
            _studentList.SelectedIndexChanged += OnStudentSelected;
            left.Controls.Add(_studentList);

            var right = new Card { Left = 380, Top = 20, Width = 360, Height = 500 };
            Controls.Add(right);

            right.Controls.Add(new Label { Text = "Selected Student", Left = 20, Top = 16, AutoSize = true, Font = Palette.Caption, ForeColor = Palette.Muted });
            _currentCardLabel = new Label { Text = "Choose a student on the left.", Left = 20, Top = 40, Width = 320, Height = 60, Font = Palette.BodyBold, ForeColor = Palette.Text };
            right.Controls.Add(_currentCardLabel);

            _unassignButton = RoundedButton.Danger("Unassign Current Card", 320, 36);
            _unassignButton.Left = 20;
            _unassignButton.Top = 108;
            _unassignButton.Visible = false;
            _unassignButton.Click += OnUnassignClick;
            right.Controls.Add(_unassignButton);

            _scanCard = new Card { Left = 20, Top = 160, Width = 320, Height = 300, Enabled = false };
            right.Controls.Add(_scanCard);

            _scanInstructionLabel = new Label
            {
                Text = "Select a student, then hand them the reader.",
                Left = 20, Top = 20, Width = 280, Height = 60, Font = Palette.Body, ForeColor = Palette.Muted
            };
            _scanCard.Controls.Add(_scanInstructionLabel);

            _capturedUidLabel = new Label
            {
                Text = "—",
                Left = 20, Top = 90, Width = 280, Height = 50,
                Font = new Font("Consolas", 20, FontStyle.Bold), ForeColor = Palette.Text,
                TextAlign = ContentAlignment.MiddleCenter
            };
            _scanCard.Controls.Add(_capturedUidLabel);

            _confirmButton = RoundedButton.Primary("Confirm Assignment", 280, 44);
            _confirmButton.Left = 20;
            _confirmButton.Top = 160;
            _confirmButton.Enabled = false;
            _confirmButton.Click += OnConfirmClick;
            _scanCard.Controls.Add(_confirmButton);
        }

        private void LoadStudents(string search)
        {
            Cursor = Cursors.WaitCursor;
            try
            {
                var students = _sync.PullStudents(null, search, false);
                _studentList.DataSource = students;
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

        private void OnStudentSelected(object sender, EventArgs e)
        {
            _selectedStudent = _studentList.SelectedItem as StudentOption;
            _capturedUid = null;
            _capturedUidLabel.Text = "—";
            _confirmButton.Enabled = false;

            if (_selectedStudent == null)
            {
                _currentCardLabel.Text = "Choose a student on the left.";
                _unassignButton.Visible = false;
                _scanCard.Enabled = false;
                return;
            }

            var existing = _store.State.CardAssignments.FirstOrDefault(a =>
                string.Equals(a.StudentId, _selectedStudent.Id, StringComparison.OrdinalIgnoreCase) &&
                string.Equals(a.Status, "active", StringComparison.OrdinalIgnoreCase));

            _currentCardLabel.Text = existing != null
                ? _selectedStudent.Name + "\nCurrent card: " + existing.CardUid
                : _selectedStudent.Name + "\nNo card assigned yet.";
            _unassignButton.Visible = existing != null;
            _scanCard.Enabled = true;
            _scanInstructionLabel.Text = "Ask " + _selectedStudent.Name + " to scan their card now.";
        }

        // Section 1's shared IRfidReader interface, same as the live feed - this
        // form just intercepts the scan instead of MainForm (see AssignmentModeActive).
        private void OnScan(object sender, CardScannedEventArgs e)
        {
            if (_selectedStudent == null) return;
            _capturedUid = e.Uid;
            _capturedUidLabel.Text = e.Uid;
            _confirmButton.Enabled = true;
        }

        private void OnConfirmClick(object sender, EventArgs e)
        {
            AttemptAssign(force: false);
        }

        private void AttemptAssign(bool force)
        {
            if (_selectedStudent == null || string.IsNullOrEmpty(_capturedUid)) return;

            Cursor = Cursors.WaitCursor;
            try
            {
                _sync.AssignCard(_capturedUid, _selectedStudent.Id, _selectedStudent.Name, force);
                MessageBox.Show(this, "Card " + _capturedUid + " assigned to " + _selectedStudent.Name + ".", "Card Assigned", MessageBoxButtons.OK, MessageBoxIcon.Information);
                _capturedUid = null;
                _capturedUidLabel.Text = "—";
                _confirmButton.Enabled = false;
                OnStudentSelected(this, EventArgs.Empty);
            }
            catch (CardAssignmentConflictException ex)
            {
                Cursor = Cursors.Default;
                var result = MessageBox.Show(
                    this,
                    ex.Message + "\r\n\r\nReassign this card to " + _selectedStudent.Name + "? The previous link will be revoked.",
                    "Card Already Assigned",
                    MessageBoxButtons.YesNo,
                    MessageBoxIcon.Warning);
                if (result == DialogResult.Yes) AttemptAssign(force: true);
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

        private void OnUnassignClick(object sender, EventArgs e)
        {
            if (_selectedStudent == null) return;
            var confirm = MessageBox.Show(this, "Unassign the current card from " + _selectedStudent.Name + "?", "Unassign Card", MessageBoxButtons.YesNo, MessageBoxIcon.Question);
            if (confirm != DialogResult.Yes) return;

            Cursor = Cursors.WaitCursor;
            try
            {
                _sync.RevokeCard(null, _selectedStudent.Id);
                OnStudentSelected(this, EventArgs.Empty);
            }
            catch (CloudAuthExpiredException)
            {
                MessageBox.Show(this, "Your sign-in has expired. Close this window and sign in again.", "Sign-in Expired", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            }
            catch (Exception ex)
            {
                MessageBox.Show(this, ex.Message, "Could Not Unassign Card", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            }
            finally
            {
                Cursor = Cursors.Default;
            }
        }
    }
}
