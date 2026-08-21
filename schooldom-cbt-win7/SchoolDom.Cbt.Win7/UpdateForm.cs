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
            // Sized to fit comfortably on a 1366x768 laptop screen (with room for the
            // taskbar) at the default size, but the form is resizable/maximizable and
            // every control below reflows via Dock/TableLayoutPanel/FlowLayoutPanel
            // instead of fixed pixel coordinates, so nothing clips on smaller screens,
            // higher DPI scaling, or if the user resizes the window.
            Width           = 1000;
            Height          = 680;
            MinimumSize     = new Size(720, 480);
            StartPosition   = FormStartPosition.CenterScreen;
            BackColor       = Palette.Background;
            Font            = new Font("Segoe UI", 10);
            AutoScaleMode   = AutoScaleMode.None;
            FormBorderStyle = FormBorderStyle.Sizable;
            MaximizeBox     = true;
            try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch { }

            Build();
        }

        // ------------------------------------------------------------------ UI
        //
        // Everything below reflows instead of using fixed pixel coordinates: the
        // hero/content split is a two-column TableLayoutPanel, every label is
        // AutoSize (so its box always matches its actually-rendered text at
        // whatever font/DPI is in effect - the old fixed Height = size * 4.5f
        // guess is what was clipping "Update Available" and other headings),
        // and the card's rows are AutoSize except the release-notes box, which
        // is the one row that absorbs remaining space and scrolls internally
        // (RichTextBox already has its own vertical scrollbar) rather than the
        // window ever hiding content.
        private void Build()
        {
            var root = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2, RowCount = 1 };
            root.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 300f));
            root.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100f));
            root.RowStyles.Add(new RowStyle(SizeType.Percent, 100f));
            Controls.Add(root);

            // ---- Left hero panel ----------------------------------------
            var hero = new Panel { Dock = DockStyle.Fill, BackColor = Palette.Navy, AutoScroll = true };
            var heroFlow = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.TopDown,
                WrapContents  = false,
                AutoSize      = true,
                AutoSizeMode  = AutoSizeMode.GrowAndShrink,
                Padding       = new Padding(34, 40, 20, 24),
                Margin        = Padding.Empty,
                MaximumSize   = new Size(260, 0),
            };
            heroFlow.Controls.Add(AutoLbl("SchoolDom", 22, true, Color.White, new Padding(0, 0, 0, 2)));
            heroFlow.Controls.Add(AutoLbl("Admin Sync Win7", 11, false, Palette.SoftText, new Padding(0, 0, 0, 36)));
            heroFlow.Controls.Add(AutoLbl("⬆", 34, false, Color.FromArgb(255, 200, 60), new Padding(0, 0, 0, 8)));
            heroFlow.Controls.Add(AutoLbl("Update Available", 16, true, Color.White, new Padding(0, 0, 0, 14)));
            heroFlow.Controls.Add(new Label
            {
                Text        = "A newer version of SchoolDom Admin Sync has been released.\n\nUpdate now to receive the latest exam sync improvements and fixes.",
                AutoSize    = true,
                MaximumSize = new Size(210, 0),
                ForeColor   = Palette.SoftText,
                Font        = new Font("Segoe UI", 10),
                BackColor   = Color.Transparent,
                Margin      = Padding.Empty,
            });
            hero.Controls.Add(heroFlow);
            root.Controls.Add(hero, 0, 0);

            // ---- Right content area -------------------------------------
            var contentOuter = new Panel { Dock = DockStyle.Fill, BackColor = Palette.Background, Padding = new Padding(28), AutoScroll = true };
            root.Controls.Add(contentOuter, 1, 0);

            var card = new TableLayoutPanel
            {
                Dock        = DockStyle.Fill,
                ColumnCount = 1,
                BackColor   = Color.White,
                Padding     = new Padding(32, 26, 32, 22),
            };
            card.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100f));
            card.Paint += (s, e) =>
            {
                using (var pen = new Pen(Palette.Border))
                    e.Graphics.DrawRectangle(pen, 0, 0, card.Width - 1, card.Height - 1);
            };
            contentOuter.Controls.Add(card);

            // Heading
            AddCardRow(card, AutoLbl("Update Available", 19, true, Palette.Text, new Padding(0, 0, 0, 18)));

            // Version comparison: "Current  →  Latest"
            var vRow = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.LeftToRight,
                WrapContents  = true,
                AutoSize      = true,
                AutoSizeMode  = AutoSizeMode.GrowAndShrink,
                Margin        = new Padding(0, 0, 0, 16),
            };
            vRow.Controls.Add(VersionChip("Current", _currentVersion, Palette.Muted));
            vRow.Controls.Add(new Label
            {
                Text      = "→",
                AutoSize  = true,
                Font      = new Font("Segoe UI", 13),
                ForeColor = Palette.Muted,
                Margin    = new Padding(14, 32, 14, 0),
            });
            vRow.Controls.Add(VersionChip("Latest", _info.LatestVersion, Palette.Green));
            AddCardRow(card, vRow);

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
                AddCardRow(card, AutoLbl(meta.ToString(), 9, false, Palette.Muted, new Padding(0, 0, 0, 14)));
            }

            // Divider
            AddCardRow(card, new Panel { Height = 1, BackColor = Palette.Border, Margin = new Padding(0, 0, 0, 16) });

            // Release notes - the one row that grows/shrinks with the window and
            // scrolls internally instead of ever clipping the rows around it.
            if (!string.IsNullOrWhiteSpace(_info.ReleaseNotes))
            {
                AddCardRow(card, AutoLbl("What’s New", 11, true, Palette.Text, new Padding(0, 0, 0, 8)));

                var notes = new RichTextBox
                {
                    BorderStyle = BorderStyle.None,
                    BackColor   = Color.FromArgb(248, 250, 253),
                    ForeColor   = Palette.Text,
                    Font        = new Font("Segoe UI", 10),
                    ReadOnly    = true,
                    ScrollBars  = RichTextBoxScrollBars.Vertical,
                    Text        = _info.ReleaseNotes,
                    Margin      = new Padding(0, 0, 0, 16),
                };
                AddCardRow(card, notes, percent: true);
            }

            // Progress bar (hidden until download starts)
            _progressBar = new ProgressBar
            {
                Minimum = 0,
                Maximum = 100,
                Visible = false,
                Style   = ProgressBarStyle.Continuous,
                Height  = 18,
                Margin  = new Padding(0, 0, 0, 8),
            };
            AddCardRow(card, _progressBar);

            // Status label
            _statusLabel = new Label
            {
                Text      = "",
                AutoSize  = true,
                ForeColor = Palette.Muted,
                Font      = new Font("Segoe UI", 9),
                Margin    = new Padding(0, 0, 0, 16),
            };
            AddCardRow(card, _statusLabel);

            // Buttons - a wrapping flow so narrow windows stack them instead of
            // clipping or overlapping.
            var buttonRow = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.LeftToRight,
                WrapContents  = true,
                AutoSize      = true,
                AutoSizeMode  = AutoSizeMode.GrowAndShrink,
            };

            _updateBtn = MakeButton("Update Now", Palette.Blue, Color.White, bold: true, flatBorder: false);
            _updateBtn.Click += OnUpdateNow;
            buttonRow.Controls.Add(_updateBtn);

            if (!_info.IsMandatory)
            {
                _laterBtn = MakeButton("Remind Me Later", Palette.LightButton, Palette.Text, bold: false, flatBorder: true);
                _laterBtn.Click += (s, e) =>
                {
                    UpdateService.SnoozeUpdate();
                    DialogResult = DialogResult.Cancel;
                    Close();
                };
                buttonRow.Controls.Add(_laterBtn);
            }

            _exitBtn = MakeButton("Exit Application", Color.White, Palette.Muted, bold: false, flatBorder: true);
            _exitBtn.Click += (s, e) => { DialogResult = DialogResult.Abort; Close(); };
            buttonRow.Controls.Add(_exitBtn);

            AddCardRow(card, buttonRow);
        }

        // Adds a control as the next row of a single-column TableLayoutPanel,
        // docked to fill its cell. percent=true marks the one row (release
        // notes) that should absorb whatever space the AutoSize rows don't need.
        private static void AddCardRow(TableLayoutPanel card, Control control, bool percent = false)
        {
            control.Dock = DockStyle.Fill;
            card.RowStyles.Add(percent ? new RowStyle(SizeType.Percent, 100f) : new RowStyle(SizeType.AutoSize));
            card.Controls.Add(control);
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
                // /VERYSILENT suppresses every dialog Inno Setup would otherwise show,
                // including a failure to overwrite the running exe (e.g. antivirus still
                // holding a file lock a beat after this process asked to close) - without
                // /LOG that kind of failure is invisible: the postinstall [Run] entry still
                // relaunches whatever ends up at {app}, which if the copy silently failed is
                // just the unchanged old exe, so this same update prompt reappears forever
                // with no visible error anywhere. The log gives something to check instead.
                var logPath = Path.Combine(Path.GetTempPath(), "SchoolDomUpdate", "install.log");
                Process.Start(new ProcessStartInfo(installerPath)
                {
                    Arguments      = "/VERYSILENT /NORESTART /CLOSEAPPLICATIONS /LOG=\"" + logPath + "\"",
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
        private static Control VersionChip(string caption, string version, Color versionColor)
        {
            var chip = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.TopDown,
                WrapContents  = false,
                AutoSize      = true,
                AutoSizeMode  = AutoSizeMode.GrowAndShrink,
                Margin        = new Padding(0, 0, 24, 0),
            };
            chip.Controls.Add(new Label
            {
                Text      = caption,
                AutoSize  = true,
                ForeColor = Palette.Muted,
                Font      = new Font("Segoe UI", 8),
                Margin    = new Padding(0, 0, 0, 2),
            });
            chip.Controls.Add(new Label
            {
                Text      = "v" + (version ?? "—"),
                AutoSize  = true,
                ForeColor = versionColor,
                Font      = new Font("Segoe UI", 13, FontStyle.Bold),
                Margin    = Padding.Empty,
            });
            return chip;
        }

        private static string FormatBytes(long bytes)
        {
            if (bytes >= 1024L * 1024) return (bytes / (1024.0 * 1024.0)).ToString("F1") + " MB";
            if (bytes >= 1024)         return (bytes / 1024.0).ToString("F1") + " KB";
            return bytes + " B";
        }

        // AutoSize means the Label's box always matches whatever size the text
        // actually renders at (font substitution, DPI scaling, ...) instead of a
        // guessed fixed Height that could clip a heading on some machines but
        // not others.
        private static Label AutoLbl(string text, float size, bool bold, Color color, Padding margin)
        {
            return new Label
            {
                Text      = text,
                AutoSize  = true,
                ForeColor = color,
                Font      = new Font("Segoe UI", size, bold ? FontStyle.Bold : FontStyle.Regular),
                BackColor = Color.Transparent,
                Margin    = margin,
            };
        }

        private static Button MakeButton(string text, Color backColor, Color foreColor, bool bold, bool flatBorder)
        {
            var button = new Button
            {
                Text         = text,
                AutoSize     = true,
                AutoSizeMode = AutoSizeMode.GrowAndShrink,
                MinimumSize  = new Size(140, 40),
                Padding      = new Padding(18, 0, 18, 0),
                BackColor    = backColor,
                ForeColor    = foreColor,
                FlatStyle    = FlatStyle.Flat,
                Font         = new Font("Segoe UI", 10, bold ? FontStyle.Bold : FontStyle.Regular),
                Cursor       = Cursors.Hand,
                Margin       = new Padding(0, 0, 12, 12),
            };
            if (flatBorder) button.FlatAppearance.BorderColor = Palette.Border;
            else button.FlatAppearance.BorderSize = 0;
            return button;
        }
    }
}
