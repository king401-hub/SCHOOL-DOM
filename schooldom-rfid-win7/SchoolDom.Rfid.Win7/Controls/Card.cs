using System.Drawing;
using System.Drawing.Drawing2D;
using System.Windows.Forms;

namespace SchoolDom.Rfid.Win7.Controls
{
    // Rounded, bordered panel used as the building block for every dashboard section.
    // WinForms has no real drop-shadow without a layered window, so the "elevated" look
    // here comes from the rounded corner + a 1px border + generous internal padding
    // instead - reads as clean/modern without extra dependencies or window-layering hacks.
    internal sealed class Card : Panel
    {
        private const int CornerRadius = 12;

        // The color actually painted inside the rounded shape (see OnPaint) - not
        // the same as this.BackColor, which stays Palette.Background (the area
        // outside the rounded corners). A child control that needs to blend its own
        // corners against what a Card actually shows (see RoundedButton) should read
        // this, not Parent.BackColor.
        public static readonly Color SurfaceColor = Palette.Surface;

        public Card()
        {
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.UserPaint | ControlStyles.ResizeRedraw | ControlStyles.OptimizedDoubleBuffer, true);
            BackColor = Palette.Background;
            Padding = new Padding(20);
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            var g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            var rect = new Rectangle(0, 0, Width - 1, Height - 1);
            using (var path = RoundedRect(rect, CornerRadius))
            {
                using (var brush = new SolidBrush(Palette.Surface))
                    g.FillPath(brush, path);
                using (var pen = new Pen(Palette.Border))
                    g.DrawPath(pen, path);
            }
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
