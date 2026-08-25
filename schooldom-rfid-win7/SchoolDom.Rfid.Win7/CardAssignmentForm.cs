using System;
using System.Drawing;
using System.Linq;
using System.Windows.Forms;
using SchoolDom.Rfid.Win7.Controls;

namespace SchoolDom.Rfid.Win7
{
    // Section 4b (single-person assign) + Section 4d (reassignment/revocation).
    // Searches across every role at the school (student/teacher/admin - admins
    // can assign themselves a card too), unlike BulkAssignForm which is
    // deliberately student-only (it's built around "class", a concept staff
    // don't have). Puts the reader into "listening mode" (Section 4b: "reuse
    // the RfidReader interface from Section 1 - works with either HID or SDK
    // reader, whichever is connected") by setting ReaderManager.AssignmentModeActive
    // so MainForm's normal attendance handling steps aside for scans captured here.
    internal sealed class CardAssignmentForm : Form
    {
        private readonly ReaderManager _readerManager;
        private readonly SyncService _sync;
        private readonly LocalStore _store;

        private TextBox _searchBox;
        private ListBox _peopleList;
        private Label _currentCardLabel;
        private RoundedButton _unassignButton;
        private Card _scanCard;
        private Label _scanInstructionLabel;
        private Label _capturedUidLabel;
        private RoundedButton _confirmButton;

        private PersonOption _selectedPerson;
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
                LoadPeople("");
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

            left.Controls.Add(new Label { Text = "Find a student, teacher, or admin", Left = 0, Top = 0, AutoSize = true, Font = Palette.BodyBold, ForeColor = Palette.Text });
            _searchBox = new TextBox { Left = 0, Top = 28, Width = 340, Height = 34, Font = new Font("Segoe UI", 11), BorderStyle = BorderStyle.FixedSingle };
            _searchBox.TextChanged += (s, e) => { _searchDebounce.Stop(); _searchDebounce.Start(); };
            _searchDebounce.Tick += (s, e) => { _searchDebounce.Stop(); LoadPeople(_searchBox.Text.Trim()); };
            left.Controls.Add(_searchBox);

            _peopleList = new ListBox { Left = 0, Top = 70, Width = 340, Height = 430, Font = Palette.Body, BorderStyle = BorderStyle.FixedSingle, IntegralHeight = false };
            _peopleList.SelectedIndexChanged += OnPersonSelected;
            left.Controls.Add(_peopleList);

            var right = new Card { Left = 380, Top = 20, Width = 360, Height = 500 };
            Controls.Add(right);

            right.Controls.Add(new Label { Text = "Selected Person", Left = 20, Top = 16, AutoSize = true, Font = Palette.Caption, ForeColor = Palette.Muted });
            _currentCardLabel = new Label { Text = "Choose someone on the left.", Left = 20, Top = 40, Width = 320, Height = 60, Font = Palette.BodyBold, ForeColor = Palette.Text };
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
                Text = "Select a person, then hand them the reader.",
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

        private void LoadPeople(string search)
        {
            Cursor = Cursors.WaitCursor;
            try
            {
                // roles: null -> every assignable role (student/teacher/staff/admin).
                var people = _sync.PullPeople(null, search, null, false);
                _peopleList.DataSource = people;
            }
            catch (CloudAuthExpiredException)
            {
                MessageBox.Show(this, "Your sign-in has expired. Close this window and sign in again.", "Sign-in Expired", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            }
            catch (Exception ex)
            {
                MessageBox.Show(this, ex.Message, "Could Not Load People", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            }
            finally
            {
                Cursor = Cursors.Default;
            }
        }

        private void OnPersonSelected(object sender, EventArgs e)
        {
            _selectedPerson = _peopleList.SelectedItem as PersonOption;
            _capturedUid = null;
            _capturedUidLabel.Text = "—";
            _confirmButton.Enabled = false;

            if (_selectedPerson == null)
            {
                _currentCardLabel.Text = "Choose someone on the left.";
                _unassignButton.Visible = false;
                _scanCard.Enabled = false;
                return;
            }

            CardAssignmentRecord existing;
            lock (_store.StateLock)
            {
                existing = _store.State.CardAssignments.FirstOrDefault(a =>
                    string.Equals(a.PersonId, _selectedPerson.Id, StringComparison.OrdinalIgnoreCase) &&
                    string.Equals(a.Status, "active", StringComparison.OrdinalIgnoreCase));
            }

            var label = _selectedPerson.Name + (string.IsNullOrEmpty(_selectedPerson.RoleLabel) ? "" : " (" + _selectedPerson.RoleLabel + ")");
            _currentCardLabel.Text = existing != null
                ? label + "\nCurrent card: " + existing.CardUid
                : label + "\nNo card assigned yet.";
            _unassignButton.Visible = existing != null;
            _scanCard.Enabled = true;
            _scanInstructionLabel.Text = "Ask " + _selectedPerson.Name + " to scan their card now.";
        }

        // Section 1's shared IRfidReader interface, same as the live feed - this
        // form just intercepts the scan instead of MainForm (see AssignmentModeActive).
        private void OnScan(object sender, CardScannedEventArgs e)
        {
            if (_selectedPerson == null) return;
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
            if (_selectedPerson == null || string.IsNullOrEmpty(_capturedUid)) return;

            Cursor = Cursors.WaitCursor;
            try
            {
                _sync.AssignCard(_capturedUid, _selectedPerson.Id, _selectedPerson.Name, _selectedPerson.Role, force);
                MessageBox.Show(this, "Card " + _capturedUid + " assigned to " + _selectedPerson.Name + ".", "Card Assigned", MessageBoxButtons.OK, MessageBoxIcon.Information);
                _capturedUid = null;
                _capturedUidLabel.Text = "—";
                _confirmButton.Enabled = false;
                OnPersonSelected(this, EventArgs.Empty);
            }
            catch (CardAssignmentConflictException ex)
            {
                Cursor = Cursors.Default;
                var result = MessageBox.Show(
                    this,
                    ex.Message + "\r\n\r\nReassign this card to " + _selectedPerson.Name + "? The previous link will be revoked.",
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
            if (_selectedPerson == null) return;
            var confirm = MessageBox.Show(this, "Unassign the current card from " + _selectedPerson.Name + "?", "Unassign Card", MessageBoxButtons.YesNo, MessageBoxIcon.Question);
            if (confirm != DialogResult.Yes) return;

            Cursor = Cursors.WaitCursor;
            try
            {
                _sync.RevokeCard(null, _selectedPerson.Id);
                OnPersonSelected(this, EventArgs.Empty);
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
