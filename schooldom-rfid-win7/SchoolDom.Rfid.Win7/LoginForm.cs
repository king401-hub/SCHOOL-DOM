using System;
using System.Drawing;
using System.Windows.Forms;
using SchoolDom.Rfid.Win7.Controls;

namespace SchoolDom.Rfid.Win7
{
    // Shown at startup whenever there's no saved access token, and again whenever
    // SyncService throws CloudAuthExpiredException. No device-pairing token here -
    // the desktop app authenticates exactly like every other SchoolDom client
    // (POST /api/auth/login/), by design (QR pairing was dropped from scope).
    internal sealed class LoginForm : Form
    {
        private readonly SyncService _sync;
        private TextBox _emailBox;
        private TextBox _passwordBox;
        private TextBox _schoolCodeBox;
        private Label _errorLabel;
        private RoundedButton _signInButton;

        public LoginForm(SyncService sync)
        {
            _sync = sync;
            Text = "Sign in to SchoolDom";
            Width = 460;
            Height = 480;
            FormBorderStyle = FormBorderStyle.FixedDialog;
            MaximizeBox = false;
            MinimizeBox = false;
            StartPosition = FormStartPosition.CenterScreen;
            BackColor = Palette.Surface;
            Font = Palette.Body;

            BuildLayout();
        }

        private void BuildLayout()
        {
            var header = new Panel { Dock = DockStyle.Top, Height = 96, BackColor = Palette.Navy };
            header.Controls.Add(new Label
            {
                Text = "SchoolDom RFID Attendance",
                Left = 28, Top = 24, AutoSize = true, Font = Palette.Title, ForeColor = Color.White
            });
            header.Controls.Add(new Label
            {
                Text = "Sign in with your admin/staff account",
                Left = 28, Top = 58, AutoSize = true, Font = Palette.Body, ForeColor = Palette.SoftText
            });
            Controls.Add(header);

            var body = new Panel { Left = 0, Top = 96, Width = 460, Height = 384, BackColor = Palette.Surface };
            Controls.Add(body);

            body.Controls.Add(FieldLabel("Email", 28, 24));
            _emailBox = TextField(28, 48, 396);
            body.Controls.Add(_emailBox);

            body.Controls.Add(FieldLabel("Password", 28, 96));
            _passwordBox = TextField(28, 120, 338);
            _passwordBox.UseSystemPasswordChar = true;
            body.Controls.Add(_passwordBox);
            body.Controls.Add(PasswordRevealToggle(_passwordBox, 28 + 338 + 4, 120));

            body.Controls.Add(FieldLabel("School code (only if your account is linked to more than one school)", 28, 168));
            _schoolCodeBox = TextField(28, 194, 396);
            body.Controls.Add(_schoolCodeBox);

            _errorLabel = new Label
            {
                Left = 28, Top = 236, Width = 396, Height = 40, AutoSize = false,
                Font = Palette.Caption, ForeColor = Palette.Coral, Visible = false
            };
            body.Controls.Add(_errorLabel);

            _signInButton = RoundedButton.Primary("Sign In", 396, 44);
            _signInButton.Left = 28;
            _signInButton.Top = 288;
            _signInButton.Click += OnSignInClick;
            body.Controls.Add(_signInButton);

            AcceptButton = _signInButton;
            _emailBox.Focus();
        }

        private static Label FieldLabel(string text, int left, int top)
        {
            return new Label { Text = text, Left = left, Top = top, AutoSize = true, Font = Palette.Caption, ForeColor = Palette.Muted };
        }

        private static TextBox TextField(int left, int top, int width)
        {
            return new TextBox
            {
                Left = left, Top = top, Width = width, Height = 34,
                Font = new Font("Segoe UI", 11), BorderStyle = BorderStyle.FixedSingle
            };
        }

        // Plain "Show"/"Hide" text, deliberately not an eye glyph - Segoe UI
        // Symbol's eye icon doesn't render reliably on Windows 7 (same reasoning
        // as SchoolDom.Cbt.Win7's PasswordRevealToggle, mirrored here for the same
        // Win7/8/10/11 support requirement).
        private static Button PasswordRevealToggle(TextBox box, int left, int top)
        {
            var toggle = new Button
            {
                Text = "Show",
                Left = left,
                Top = top,
                Width = 54,
                Height = 34,
                FlatStyle = FlatStyle.Flat,
                BackColor = Palette.LightButton,
                ForeColor = Palette.Text,
                Font = new Font("Segoe UI", 8, FontStyle.Bold),
                Cursor = Cursors.Hand,
                TabStop = false,
            };
            toggle.FlatAppearance.BorderColor = Palette.Border;
            toggle.Click += (s, e) =>
            {
                box.UseSystemPasswordChar = !box.UseSystemPasswordChar;
                toggle.Text = box.UseSystemPasswordChar ? "Show" : "Hide";
            };
            return toggle;
        }

        private void OnSignInClick(object sender, EventArgs e)
        {
            var email = _emailBox.Text.Trim();
            var password = _passwordBox.Text;
            if (email.Length == 0 || password.Length == 0)
            {
                ShowError("Enter your email and password.");
                return;
            }

            _signInButton.Enabled = false;
            _signInButton.Text = "Signing in...";
            Cursor = Cursors.WaitCursor;
            try
            {
                _sync.Login("https://schooldom.academy", email, password, _schoolCodeBox.Text.Trim());
                DialogResult = DialogResult.OK;
                Close();
            }
            catch (Exception ex)
            {
                ShowError(ex.Message);
            }
            finally
            {
                Cursor = Cursors.Default;
                _signInButton.Enabled = true;
                _signInButton.Text = "Sign In";
            }
        }

        private void ShowError(string message)
        {
            _errorLabel.Text = message;
            _errorLabel.Visible = true;
        }
    }
}
