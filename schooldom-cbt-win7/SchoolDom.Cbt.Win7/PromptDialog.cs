using System.Windows.Forms;

namespace SchoolDom.Cbt.Win7
{
    public static class PromptDialog
    {
        public static string Show(string title, string label, bool password)
        {
            using (var form = new Form())
            using (var text = new TextBox())
            using (var ok = new Button())
            using (var cancel = new Button())
            using (var prompt = new Label())
            {
                form.Text = title;
                form.Width = 420;
                form.Height = 165;
                form.StartPosition = FormStartPosition.CenterParent;
                form.FormBorderStyle = FormBorderStyle.FixedDialog;
                form.MaximizeBox = false;
                form.MinimizeBox = false;

                prompt.Left = 16;
                prompt.Top = 16;
                prompt.Width = 360;
                prompt.Text = label;

                text.Left = 16;
                text.Top = 44;
                text.Width = 370;
                text.UseSystemPasswordChar = password;

                ok.Text = "OK";
                ok.Left = 214;
                ok.Top = 82;
                ok.Width = 88;
                ok.DialogResult = DialogResult.OK;

                cancel.Text = "Cancel";
                cancel.Left = 308;
                cancel.Top = 82;
                cancel.Width = 88;
                cancel.DialogResult = DialogResult.Cancel;

                form.Controls.Add(prompt);
                form.Controls.Add(text);
                form.Controls.Add(ok);
                form.Controls.Add(cancel);
                form.AcceptButton = ok;
                form.CancelButton = cancel;

                return form.ShowDialog() == DialogResult.OK ? text.Text : "";
            }
        }
    }
}

