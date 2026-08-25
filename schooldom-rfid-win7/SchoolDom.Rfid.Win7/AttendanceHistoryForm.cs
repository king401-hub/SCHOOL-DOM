using System;
using System.Drawing;
using System.Windows.Forms;
using SchoolDom.Rfid.Win7.Controls;

namespace SchoolDom.Rfid.Win7
{
    // Shows RFID-sourced attendance pulled fresh from the server - merges
    // student (academic.AttendanceRecord) and staff (attendance.TeacherAttendance)
    // rows server-side (see rfid_attendance.views.attendance_history), so this
    // form doesn't need to know which table a row actually lives in.
    internal sealed class AttendanceHistoryForm : Form
    {
        private readonly SyncService _sync;
        private DateTimePicker _datePicker;
        private CheckBox _allRecentCheckBox;
        private ListView _list;
        private Label _emptyLabel;

        public AttendanceHistoryForm(SyncService sync)
        {
            _sync = sync;

            Text = "Attendance History";
            Width = 900;
            Height = 620;
            StartPosition = FormStartPosition.CenterParent;
            BackColor = Palette.Background;
            Font = Palette.Body;
            MinimumSize = new Size(700, 480);

            BuildLayout();
            Load += (s, e) => LoadHistory();
        }

        private void BuildLayout()
        {
            var header = new Label { Text = "Attendance History", Left = 20, Top = 20, AutoSize = true, Font = Palette.Title, ForeColor = Palette.Text };
            Controls.Add(header);

            _datePicker = new DateTimePicker
            {
                Left = 20, Top = 60, Width = 180, Height = 34,
                Font = new Font("Segoe UI", 10), Format = DateTimePickerFormat.Short
            };
            _datePicker.ValueChanged += (s, e) => { _allRecentCheckBox.Checked = false; LoadHistory(); };
            Controls.Add(_datePicker);

            _allRecentCheckBox = new CheckBox
            {
                Text = "Last 7 days instead", Left = 212, Top = 66, AutoSize = true,
                Font = Palette.Body, ForeColor = Palette.Text, Checked = true
            };
            _allRecentCheckBox.CheckedChanged += (s, e) => LoadHistory();
            Controls.Add(_allRecentCheckBox);

            var card = new Card { Left = 20, Top = 108, Width = 840, Height = 464, Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Bottom };
            Controls.Add(card);

            _list = BuildListView();
            _list.Left = 16;
            _list.Top = 16;
            _list.Width = 808;
            _list.Height = 432;
            _list.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Bottom;
            card.Controls.Add(_list);

            _emptyLabel = new Label
            {
                Text = "No RFID attendance recorded in this period yet.",
                Left = 16, Top = 16, Width = 780, Height = 30,
                Font = Palette.Body, ForeColor = Palette.Muted, Visible = false
            };
            card.Controls.Add(_emptyLabel);
        }

        private ListView BuildListView()
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
            list.Columns.Add("Person", 220);
            list.Columns.Add("Role", 110);
            list.Columns.Add("Date", 100);
            list.Columns.Add("Clock In", 100);
            list.Columns.Add("Clock Out", 100);
            list.Columns.Add("Card UID", 150);

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
                var entry = e.Item.Tag as AttendanceHistoryEntry;
                var rowBack = e.ItemIndex % 2 == 0 ? Palette.Surface : Palette.Background;
                using (var brush = new SolidBrush(rowBack))
                    e.Graphics.FillRectangle(brush, e.Bounds);
                if (entry == null) return;

                string text;
                var font = Palette.Body;
                var color = Palette.Text;
                switch (e.ColumnIndex)
                {
                    case 0: text = entry.PersonName; font = Palette.BodyBold; break;
                    case 1: text = FormatRole(entry.Role); color = Palette.Muted; break;
                    case 2: text = entry.ClockInAt.HasValue ? entry.ClockInAt.Value.ToString("MMM d") : "—"; color = Palette.Muted; break;
                    case 3: text = entry.ClockInAt.HasValue ? entry.ClockInAt.Value.ToString("h:mm tt") : "—"; break;
                    case 4: text = entry.ClockOutAt.HasValue ? entry.ClockOutAt.Value.ToString("h:mm tt") : "—"; color = entry.ClockOutAt.HasValue ? Palette.Text : Palette.Muted; break;
                    case 5: text = entry.CardUid; font = Palette.Mono; color = Palette.Muted; break;
                    default: text = ""; break;
                }
                TextRenderer.DrawText(e.Graphics, text, font, e.Bounds, color,
                    TextFormatFlags.Left | TextFormatFlags.VerticalCenter | TextFormatFlags.LeftAndRightPadding);
            };

            return list;
        }

        private static string FormatRole(string role)
        {
            if (string.IsNullOrEmpty(role)) return "";
            return char.ToUpperInvariant(role[0]) + role.Substring(1).Replace('_', ' ');
        }

        private void LoadHistory()
        {
            Cursor = Cursors.WaitCursor;
            try
            {
                var dateIso = _allRecentCheckBox.Checked ? null : _datePicker.Value.ToString("yyyy-MM-dd");
                var entries = _sync.PullAttendanceHistory(dateIso);

                _list.Items.Clear();
                foreach (var entry in entries)
                {
                    var item = new ListViewItem(new[] { "", "", "", "", "", "" }) { Tag = entry };
                    _list.Items.Add(item);
                }
                _emptyLabel.Visible = entries.Count == 0;
                _list.Visible = entries.Count > 0;
            }
            catch (CloudAuthExpiredException)
            {
                MessageBox.Show(this, "Your sign-in has expired. Close this window and sign in again.", "Sign-in Expired", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            }
            catch (Exception ex)
            {
                MessageBox.Show(this, ex.Message, "Could Not Load Attendance History", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            }
            finally
            {
                Cursor = Cursors.Default;
            }
        }
    }
}
