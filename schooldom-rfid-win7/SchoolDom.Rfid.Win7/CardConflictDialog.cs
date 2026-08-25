using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.IO;
using System.Net;
using System.Windows.Forms;
using SchoolDom.Rfid.Win7.Controls;

namespace SchoolDom.Rfid.Win7
{
    // Section 4d - "if a card is already assigned, show a popup of the already-
    // assigned person's name/picture/class, and require an explicit unassign
    // before it can go to someone else." Replaces the old plain-text Yes/No
    // "reassign?" MessageBox with a real identity card and a deliberate
    // two-step flow: Unassign here, then the caller retries the original
    // assignment (never a single-click "force reassign").
    internal sealed class CardConflictDialog : Form
    {
        private readonly SyncService _sync;
        private readonly string _cardUid;
        private PictureBox _photoBox;

        public bool WasUnassigned { get; private set; }

        public CardConflictDialog(SyncService sync, string cardUid, string personName, string roleLabel, string className, string photoUrl)
        {
            _sync = sync;
            _cardUid = cardUid;

            Text = "Card Already Assigned";
            Width = 460;
            Height = 380;
            FormBorderStyle = FormBorderStyle.FixedDialog;
            MaximizeBox = false;
            MinimizeBox = false;
            StartPosition = FormStartPosition.CenterParent;
            BackColor = Palette.Surface;
            Font = Palette.Body;

            BuildLayout(personName, roleLabel, className);
            LoadPhotoAsync(photoUrl);
        }

        private void BuildLayout(string personName, string roleLabel, string className)
        {
            var banner = new Panel { Dock = DockStyle.Top, Height = 70, BackColor = Palette.CoralSoft };
            banner.Controls.Add(new Label
            {
                Text = "Card " + _cardUid + " is already assigned",
                Left = 24, Top = 22, AutoSize = true, Font = Palette.BodyBold, ForeColor = Palette.Coral
            });
            Controls.Add(banner);

            _photoBox = new PictureBox
            {
                Left = 24, Top = 92, Width = 88, Height = 88,
                SizeMode = PictureBoxSizeMode.Zoom,
                BackColor = Palette.LightButton
            };
            Controls.Add(_photoBox);

            var nameLabel = new Label
            {
                Text = personName ?? "Unknown",
                Left = 128, Top = 94, Width = 300, Height = 30,
                Font = Palette.Title, ForeColor = Palette.Text
            };
            Controls.Add(nameLabel);

            var roleText = string.IsNullOrEmpty(roleLabel) ? "" : roleLabel;
            var classText = string.IsNullOrEmpty(className) ? "" : " · " + className;
            var detailLabel = new Label
            {
                Text = roleText + classText,
                Left = 128, Top = 128, Width = 300, Height = 24,
                Font = Palette.Body, ForeColor = Palette.Muted
            };
            Controls.Add(detailLabel);

            var explainLabel = new Label
            {
                Text = "This card must be unassigned from " + (personName ?? "this person") +
                       " before it can be given to someone else.",
                Left = 24, Top = 196, Width = 400, Height = 50,
                Font = Palette.Body, ForeColor = Palette.Text
            };
            Controls.Add(explainLabel);

            var unassignButton = RoundedButton.Danger("Unassign Card", 400, 44);
            unassignButton.Left = 24;
            unassignButton.Top = 256;
            unassignButton.Click += OnUnassignClick;
            Controls.Add(unassignButton);

            var cancelButton = RoundedButton.Secondary("Cancel", 400, 40);
            cancelButton.Left = 24;
            cancelButton.Top = 306;
            cancelButton.Click += (s, e) => { DialogResult = DialogResult.Cancel; Close(); };
            Controls.Add(cancelButton);
        }

        private void OnUnassignClick(object sender, EventArgs e)
        {
            Cursor = Cursors.WaitCursor;
            try
            {
                _sync.RevokeCard(_cardUid, null);
                WasUnassigned = true;
                DialogResult = DialogResult.OK;
                Close();
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

        // Downloaded off the UI thread so the dialog appears immediately instead
        // of waiting on the photo - falls back to a plain placeholder (silently)
        // if there's no photo, the request fails, or the dialog closes first.
        private void LoadPhotoAsync(string photoUrl)
        {
            if (string.IsNullOrEmpty(photoUrl)) return;

            System.Threading.ThreadPool.QueueUserWorkItem(_ =>
            {
                Image image = null;
                try
                {
                    var request = (HttpWebRequest)WebRequest.Create(photoUrl);
                    request.Timeout = 8000;
                    using (var response = (HttpWebResponse)request.GetResponse())
                    using (var stream = response.GetResponseStream())
                    using (var memory = new MemoryStream())
                    {
                        if (stream != null) stream.CopyTo(memory);
                        image = Image.FromStream(memory);
                        // Detach from the network stream's buffer immediately - the
                        // MemoryStream is about to be disposed.
                        image = new Bitmap(image);
                    }
                }
                catch
                {
                    return; // no photo on file, network hiccup, bad URL - placeholder stands
                }

                try
                {
                    if (IsDisposed || !IsHandleCreated) return;
                    BeginInvoke(new Action(() =>
                    {
                        if (!IsDisposed) _photoBox.Image = image;
                    }));
                }
                catch (ObjectDisposedException) { }
                catch (InvalidOperationException) { }
            });
        }
    }
}
