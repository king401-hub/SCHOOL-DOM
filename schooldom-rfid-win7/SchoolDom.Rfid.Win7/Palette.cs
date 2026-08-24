using System.Drawing;

namespace SchoolDom.Rfid.Win7
{
    // Same palette as SchoolDom.Cbt.Win7's internal Palette class, kept in sync deliberately
    // so every SchoolDom Win7 desktop app reads as one product family.
    internal static class Palette
    {
        public static readonly Color Background = Color.FromArgb(244, 247, 251);
        public static readonly Color Surface = Color.White;
        public static readonly Color Navy = Color.FromArgb(15, 32, 55);
        public static readonly Color SideButton = Color.FromArgb(31, 55, 87);
        public static readonly Color Text = Color.FromArgb(22, 34, 51);
        public static readonly Color Muted = Color.FromArgb(96, 112, 132);
        public static readonly Color SoftText = Color.FromArgb(196, 207, 221);
        public static readonly Color Border = Color.FromArgb(214, 223, 235);
        public static readonly Color LightButton = Color.FromArgb(235, 241, 248);
        public static readonly Color Blue = Color.FromArgb(24, 96, 180);
        public static readonly Color BlueHover = Color.FromArgb(20, 82, 156);
        public static readonly Color Green = Color.FromArgb(37, 137, 92);
        public static readonly Color GreenSoft = Color.FromArgb(224, 244, 234);
        public static readonly Color Gold = Color.FromArgb(184, 127, 33);
        public static readonly Color GoldSoft = Color.FromArgb(252, 240, 217);
        public static readonly Color Coral = Color.FromArgb(196, 74, 62);
        public static readonly Color CoralSoft = Color.FromArgb(250, 227, 224);

        public static readonly Font Display = new Font("Segoe UI", 22, FontStyle.Bold);
        public static readonly Font Title = new Font("Segoe UI", 14, FontStyle.Bold);
        public static readonly Font Subtitle = new Font("Segoe UI", 11, FontStyle.Regular);
        public static readonly Font Body = new Font("Segoe UI", 10, FontStyle.Regular);
        public static readonly Font BodyBold = new Font("Segoe UI", 10, FontStyle.Bold);
        public static readonly Font Caption = new Font("Segoe UI", 8.5f, FontStyle.Regular);
        public static readonly Font Mono = new Font("Consolas", 13, FontStyle.Bold);
    }
}
