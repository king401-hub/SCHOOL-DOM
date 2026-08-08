using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Text;
using System.Threading;
using System.Windows.Forms;

namespace SchoolDom.Cbt.Win7
{
    // DialogResult contract:
    //   OK     → installer launched; caller must exit
    //   Abort  → user chose "Exit Application"; caller must exit
    //   Cancel → user chose "Remind Me Later"; caller continues to MainForm
    internal sealed class UpdateForm : Form
    {
        private readonly string     _currentVersion;
        private readonly UpdateInfo _info;

        private Label       _statusLabel;
        private ProgressBar _progressBar;
        private Button      _updateBtn;
        private Button      _laterBtn;   // null when update is mandatory
        private Button      _exitBtn;

        internal UpdateForm(string currentVersion, UpdateInfo info)
        {
            _currentVersion = currentVersion;
            _info           = info;

            Text            = "SchoolDom Admin Sync — Update Available";
            Width           = 1280;
            Height          = 760;
            MinimumSize     = new Size(980, 620);
            StartPosition   = FormStartPosition.CenterScreen;
            BackColor       = Palette.Background;
            Font            = new Font("Segoe UI", 10);
            AutoScaleMode   = AutoScaleMode.None;
            FormBorderStyle = FormBorderStyle.FixedSingle;
            MaximizeBox     = false;
            try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch { }

            Build();
        }

        // ------------------------------------------------------------------ UI
        private void Build()
        {
            // ---- Left hero panel ----------------------------------------
            const int heroW = 420;
            const int heroLabelLeft = 38;
            const int heroLabelWidth = heroW - heroLabelLeft - 16;  // fills panel with right margin

            var hero = new Panel { Dock = DockStyle.Left, Width = heroW, BackColor = Palette.Navy };
            hero.Controls.Add(Lbl("SchoolDom",        heroLabelLeft, 46,  22, true,  heroLabelWidth, Color.White));
            hero.Controls.Add(Lbl("Admin Sync Win7",  heroLabelLeft, 94,  11, false, heroLabelWidth, Palette.SoftText));
            hero.Controls.Add(Lbl("⬆",           heroLabelLeft, 180, 40, false, 80,              Color.FromArgb(255, 200, 60)));
            hero.Controls.Add(Lbl("Update Available", heroLabelLeft, 248, 16, true,  heroLabelWidth, Color.White));

            // Multi-line description — use AutoSize so it grows to fit all lines
            var desc = new Label
            {
                Text        = "A newer version of SchoolDom Admin Sync has been released.\n\nUpdate now to receive the latest exam sync improvements and fixes.",
                Left        = heroLabelLeft,
                Top         = 300,
                MaximumSize = new Size(heroLabelWidth, 0),
                AutoSize    = true,
                ForeColor   = Palette.SoftText,
                Font        = new Font("Segoe UI", 10),
                BackColor   = Color.Transparent,
            };
            hero.Controls.Add(desc);

            // ---- Right content area -------------------------------------
            var content = new Panel { Dock = DockStyle.Fill, BackColor = Palette.Background };

            var card = new Panel
            {
                Left      = 70,
                Top       = 40,
                Width     = 640,
                Height    = 640,
                BackColor = Color.White,
            };
            card.Paint += (s, e) =>
            {
                using (var pen = new Pen(Palette.Border))
                    e.Graphics.DrawRectangle(pen, 0, 0, card.Width - 1, card.Height - 1);
            };
            content.Controls.Add(card);

            int y = 32;

            // Heading
            card.Controls.Add(Lbl("Update Available", 32, y, 19, true, 560, Palette.Text));
            y += 46;

            // Version comparison: "Current  →  Latest"
            var vRow = new Panel { Left = 32, Top = y, Width = 560, Height = 44, BackColor = Color.Transparent };
            vRow.Controls.Add(VersionChip("Current", _currentVersion, Palette.Muted, 0));
            vRow.Controls.Add(Lbl("→", 194, 14, 13, false, 26, Palette.Muted));
            vRow.Controls.Add(VersionChip("Latest",  _info.LatestVersion, Palette.Green, 228));
            card.Controls.Add(vRow);
            y += 58;

            // Meta line (date · size · mandatory badge)
            var meta = new StringBuilder();
            if (!string.IsNullOrWhiteSpace(_info.ReleaseDate))
                meta.Append("Released: ").Append(_info.ReleaseDate);
            if (_info.FileSizeBytes.HasValue)
            {
                if (meta.Length > 0) meta.Append("   ·   ");
                meta.Append("Size: ").Append(FormatBytes(_info.FileSizeBytes.Value));
            }
            if (_info.IsMandatory)
            {
                if (meta.Length > 0) meta.Append("   ·   ");
                meta.Append("⚠ Mandatory update");
            }
            if (meta.Length > 0)
            {
                card.Controls.Add(Lbl(meta.ToString(), 32, y, 9, false, 560, Palette.Muted));
                y += 26;
            }

            // Divider
            card.Controls.Add(new Panel { Left = 32, Top = y + 6, Width = 560, Height = 1, BackColor = Palette.Border });
            y += 22;

            // Release notes
            if (!string.IsNullOrWhiteSpace(_info.ReleaseNotes))
            {
                card.Controls.Add(Lbl("What’s New", 32, y, 11, true, 560, Palette.Text));
                y += 26;

                var notes = new RichTextBox
                {
                    Left        = 32,
                    Top         = y,
                    Width       = 560,
                    Height      = 180,
                    BorderStyle = BorderStyle.None,
                    BackColor   = Color.FromArgb(248, 250, 253),
                    ForeColor   = Palette.Text,
                    Font        = new Font("Segoe UI", 10),
                    ReadOnly    = true,
                    ScrollBars  = RichTextBoxScrollBars.Vertical,
                    Text        = _info.ReleaseNotes,
                };
                card.Controls.Add(notes);
                y += 196;
            }
            else
            {
                y += 16;
            }

            // Progress bar (hidden until download starts)
            _progressBar = new ProgressBar
            {
                Left    = 32,
                Top     = y,
                Width   = 560,
                Height  = 18,
                Minimum = 0,
                Maximum = 100,
                Visible = false,
                Style   = ProgressBarStyle.Continuous,
            };
            card.Controls.Add(_progressBar);
            y += 26;

            // Status label
            _statusLabel = new Label
            {
                Left      = 32,
                Top       = y,
                Width     = 560,
                Height    = 20,
                Text      = "",
                ForeColor = Palette.Muted,
                Font      = new Font("Segoe UI", 9),
                AutoSize  = false,
            };
            card.Controls.Add(_statusLabel);
            y += 34;

            // Buttons
            _updateBtn = new Button
            {
                Text      = "Update Now",
                Left      = 32,
                Top       = y,
                Width     = 166,
                Height    = 40,
                BackColor = Palette.Blue,
                ForeColor = Color.White,
                FlatStyle = FlatStyle.Flat,
                Font      = new Font("Segoe UI", 10, FontStyle.Bold),
                Cursor    = Cursors.Hand,
            };
            _updateBtn.FlatAppearance.BorderSize = 0;
            _updateBtn.Click += OnUpdateNow;
            card.Controls.Add(_updateBtn);

            int bx = 210;

            if (!_info.IsMandatory)
            {
                _laterBtn = new Button
                {
                    Text      = "Remind Me Later",
                    Left      = bx,
                    Top       = y,
                    Width     = 160,
                    Height    = 40,
                    BackColor = Palette.LightButton,
                    ForeColor = Palette.Text,
                    FlatStyle = FlatStyle.Flat,
                    Font      = new Font("Segoe UI", 10),
                    Cursor    = Cursors.Hand,
                };
                _laterBtn.FlatAppearance.BorderColor = Palette.Border;
                _laterBtn.Click += (s, e) =>
                {
                    UpdateService.SnoozeUpdate();
                    DialogResult = DialogResult.Cancel;
                    Close();
                };
                card.Controls.Add(_laterBtn);
                bx += 172;
            }

            _exitBtn = new Button
            {
                Text      = "Exit Application",
                Left      = bx,
                Top       = y,
                Width     = 154,
                Height    = 40,
                BackColor = Color.White,
                ForeColor = Palette.Muted,
                FlatStyle = FlatStyle.Flat,
                Font      = new Font("Segoe UI", 10),
                Cursor    = Cursors.Hand,
            };
            _exitBtn.FlatAppearance.BorderColor = Palette.Border;
            _exitBtn.Click += (s, e) => { DialogResult = DialogResult.Abort; Close(); };
            card.Controls.Add(_exitBtn);

            Controls.Add(content);
            Controls.Add(hero);
        }

        // ------------------------------------------------------------------ Download flow
        private void OnUpdateNow(object sender, EventArgs e)
        {
            if (string.IsNullOrWhiteSpace(_info.DownloadUrl))
            {
                MessageBox.Show(
                    "No download link is configured for this update.\n\n" +
                    "Please visit schooldom.academy to download the latest installer manually.",
                    "No Download Available",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Information);
                return;
            }

            SetBusy(true);
            SetStatus("Starting download...");

            var url      = _info.DownloadUrl;
            var version  = (_info.LatestVersion ?? "update").TrimStart('v', 'V').Trim();
            var destPath = Path.Combine(
                Path.GetTempPath(), "SchoolDomUpdate",
                "SchoolDom-Admin-Sync-Win7-" + version + "-Setup.exe");

            var thread = new Thread(() =>
            {
                try
                {
                    UpdateService.DownloadInstaller(url, destPath, pct =>
                    {
                        Invoke(new Action(() =>
                        {
                            _progressBar.Value = Math.Min(pct, 100);
                            SetStatus(pct < 100
                                ? "Downloading update… " + pct + "%"
                                : "Download complete. Launching installer…");
                        }));
                    });

                    Invoke(new Action(() => LaunchAndExit(destPath)));
                }
                catch (Exception ex)
                {
                    Invoke(new Action(() =>
                    {
                        SetBusy(false);
                        SetStatus("Download failed: " + ex.Message);
                    }));
                }
            });
            thread.IsBackground = true;
            thread.Start();
        }

        private void LaunchAndExit(string installerPath)
        {
            try
            {
                Process.Start(new ProcessStartInfo(installerPath)
                {
                    Arguments      = "/VERYSILENT /NORESTART /CLOSEAPPLICATIONS",
                    UseShellExecute = true,
                });
            }
            catch (Exception ex)
            {
                SetBusy(false);
                SetStatus("Could not launch installer: " + ex.Message
                    + "\n\nRun it manually: " + installerPath);
                return;
            }

            DialogResult = DialogResult.OK;
            Close();
        }

        private void SetBusy(bool busy)
        {
            _updateBtn.Enabled       = !busy;
            if (_laterBtn != null) _laterBtn.Enabled = !busy;
            _exitBtn.Enabled         = !busy;
            _progressBar.Visible     = busy;
        }

        private void SetStatus(string text) { _statusLabel.Text = text; }

        // ------------------------------------------------------------------ Helpers
        private static Panel VersionChip(string caption, string version, Color versionColor, int left)
        {
            var chip = new Panel { Left = left, Top = 0, Width = 200, Height = 44, BackColor = Color.Transparent };
            chip.Controls.Add(new Label
            {
                Text      = caption,
                Left = 0, Top = 0, Width = 200, Height = 18,
                ForeColor = Palette.Muted,
                Font      = new Font("Segoe UI", 8),
                AutoSize  = false,
            });
            chip.Controls.Add(new Label
            {
                Text      = "v" + (version ?? "—"),
                Left = 0, Top = 18, Width = 200, Height = 22,
                ForeColor = versionColor,
                Font      = new Font("Segoe UI", 13, FontStyle.Bold),
                AutoSize  = false,
            });
            return chip;
        }

        private static string FormatBytes(long bytes)
        {
            if (bytes >= 1024L * 1024) return (bytes / (1024.0 * 1024.0)).ToString("F1") + " MB";
            if (bytes >= 1024)         return (bytes / 1024.0).ToString("F1") + " KB";
            return bytes + " B";
        }

        private static Label Lbl(string text, int left, int top, float size, bool bold, int width, Color color)
        {
            return new Label
            {
                Text         = text,
                Left         = left,
                Top          = top,
                Width        = width,
                Height       = (int)(size * 4.5f),   // generous — prevents clipping at any DPI
                ForeColor    = color,
                Font         = new Font("Segoe UI", size, bold ? FontStyle.Bold : FontStyle.Regular),
                AutoSize     = false,
                AutoEllipsis = false,
                BackColor    = Color.Transparent,
            };
        }
    }
}
