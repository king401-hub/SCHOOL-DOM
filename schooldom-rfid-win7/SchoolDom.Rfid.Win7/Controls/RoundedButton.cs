using System.Drawing;
using System.Drawing.Drawing2D;
using System.Windows.Forms;

namespace SchoolDom.Rfid.Win7.Controls
{
    // Owner-drawn flat button with rounded corners and a real hover/press state -
    // stock WinForms Button (even with FlatStyle.Flat) stays a square with no hover
    // feedback, which is what made the CBT app's buttons feel dated. No third-party
    // control library needed for this — just GDI+.
    internal sealed class RoundedButton : Button
    {
        private const int CornerRadius = 8;
        private bool _hovering;
        private bool _pressed;

        public Color NormalBackColor { get; set; }
        public Color HoverBackColor { get; set; }
        public Color BorderColor { get; set; }

        public RoundedButton()
        {
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.UserPaint | ControlStyles.ResizeRedraw | ControlStyles.SupportsTransparentBackColor, true);
            FlatStyle = FlatStyle.Flat;
            FlatAppearance.BorderSize = 0;
            Cursor = Cursors.Hand;
            Font = Palette.BodyBold;
            NormalBackColor = Palette.Blue;
            HoverBackColor = Palette.BlueHover;
            BorderColor = Color.Transparent;
            ForeColor = Color.White;
            BackColor = Color.Transparent;

            MouseEnter += (s, e) => { _hovering = true; Invalidate(); };
            MouseLeave += (s, e) => { _hovering = false; Invalidate(); };
            MouseDown += (s, e) => { _pressed = true; Invalidate(); };
            MouseUp += (s, e) => { _pressed = false; Invalidate(); };
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            var g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;

            var fill = !Enabled
                ? Palette.LightButton
                : _pressed
                    ? ControlPaint.Dark(HoverBackColor, 0.05f)
                    : _hovering
                        ? HoverBackColor
                        : NormalBackColor;

            var rect = new Rectangle(0, 0, Width - 1, Height - 1);
            using (var path = RoundedRect(rect, CornerRadius))
            using (var brush = new SolidBrush(fill))
            {
                g.FillPath(brush, path);
                if (BorderColor != Color.Transparent)
                {
                    using (var pen = new Pen(BorderColor))
                        g.DrawPath(pen, path);
                }
            }

            var textColor = Enabled ? ForeColor : Palette.Muted;
            TextRenderer.DrawText(g, Text, Font, rect, textColor,
                TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.EndEllipsis);
        }

        private static GraphicsPath RoundedRect(Rectangle bounds, int radius)
        {
            var d = radius * 2;
            var path = new GraphicsPath();
            path.AddArc(bounds.X, bounds.Y, d, d, 180, 90);
            path.AddArc(bounds.Right - d, bounds.Y, d, d, 270, 90);
            path.AddArc(bounds.Right - d, bounds.Bottom - d, d, d, 0, 90);
            path.AddArc(bounds.X, bounds.Bottom - d, d, d, 90, 90);
            path.CloseFigure();
            return path;
        }

        public static RoundedButton Primary(string text, int width, int height = 42)
        {
            return new RoundedButton
            {
                Text = text,
                Width = width,
                Height = height,
                NormalBackColor = Palette.Blue,
                HoverBackColor = Palette.BlueHover,
                ForeColor = Color.White
            };
        }

        public static RoundedButton Secondary(string text, int width, int height = 42)
        {
            return new RoundedButton
            {
                Text = text,
                Width = width,
                Height = height,
                NormalBackColor = Palette.LightButton,
                HoverBackColor = Palette.Border,
                ForeColor = Palette.Text
            };
        }

        public static RoundedButton Danger(string text, int width, int height = 42)
        {
            return new RoundedButton
            {
                Text = text,
                Width = width,
                Height = height,
                NormalBackColor = Palette.Coral,
                HoverBackColor = ControlPaint.Dark(Palette.Coral, 0.08f),
                ForeColor = Color.White
            };
        }
    }
}
