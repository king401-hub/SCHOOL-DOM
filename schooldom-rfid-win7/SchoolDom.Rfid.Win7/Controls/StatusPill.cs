using System.Drawing;
using System.Drawing.Drawing2D;
using System.Windows.Forms;

namespace SchoolDom.Rfid.Win7.Controls
{
    // Small rounded "chip" with a colored dot + label - used for reader connection
    // status, sync queue state, and per-scan match/no-match feedback.
    internal sealed class StatusPill : Control
    {
        private Color _dotColor = Palette.Green;
        private Color _tint = Palette.GreenSoft;
        private string _text = "";

        public Color DotColor
        {
            get { return _dotColor; }
            set { _dotColor = value; Invalidate(); }
        }

        public Color Tint
        {
            get { return _tint; }
            set { _tint = value; Invalidate(); }
        }

        public override string Text
        {
            get { return _text; }
            set { _text = value ?? ""; Invalidate(); AutoSizeToContent(); }
        }

        public StatusPill()
        {
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.UserPaint | ControlStyles.ResizeRedraw | ControlStyles.OptimizedDoubleBuffer, true);
            Font = Palette.BodyBold;
            Height = 28;
            BackColor = Color.Transparent;
        }

        public void SetState(string text, Color dot, Color tint)
        {
            _dotColor = dot;
            _tint = tint;
            Text = text;
        }

        private void AutoSizeToContent()
        {
            using (var g = CreateGraphics())
            {
                var textSize = g.MeasureString(_text, Font);
                Width = (int)textSize.Width + 34;
            }
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            var g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            var rect = new Rectangle(0, 0, Width - 1, Height - 1);
            using (var path = RoundedRect(rect, Height / 2))
            using (var brush = new SolidBrush(_tint))
                g.FillPath(brush, path);

            const int dotSize = 8;
            var dotRect = new Rectangle(12, (Height - dotSize) / 2, dotSize, dotSize);
            using (var dotBrush = new SolidBrush(_dotColor))
                g.FillEllipse(dotBrush, dotRect);

            var textRect = new Rectangle(dotRect.Right + 8, 0, Width - dotRect.Right - 16, Height);
            TextRenderer.DrawText(g, _text, Font, textRect, Palette.Text,
                TextFormatFlags.Left | TextFormatFlags.VerticalCenter);
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
    }
}
