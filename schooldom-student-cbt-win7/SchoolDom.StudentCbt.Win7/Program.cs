using System;
using System.Net;
using System.Net.Security;
using System.Security.Cryptography.X509Certificates;
using System.Windows.Forms;

namespace SchoolDom.StudentCbt.Win7
{
    internal static class Program
    {
        [STAThread]
        private static void Main()
        {
            BootstrapNetworkSecurity();
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new MainForm());
        }

        // The student app talks to the admin app over a raw TCP LAN socket (no HTTPS),
        // but we set up TLS and certificate trust here anyway in case the student app
        // ever performs a cloud HTTP call (e.g. downloading a logo image).
        internal static void BootstrapNetworkSecurity()
        {
            try
            {
                ServicePointManager.SecurityProtocol =
                    (SecurityProtocolType)(192 | 768 | 3072); // Tls | Tls11 | Tls12
            }
            catch
            {
                try { ServicePointManager.SecurityProtocol = (SecurityProtocolType)(192 | 768); }
                catch
                {
                    try { ServicePointManager.SecurityProtocol = SecurityProtocolType.Tls; }
                    catch { }
                }
            }

            ServicePointManager.Expect100Continue = false;
            ServicePointManager.DefaultConnectionLimit = 16;

            // Accept chain errors caused by out-of-date root CA trust stores on Win7 RTM
            ServicePointManager.ServerCertificateValidationCallback = ValidateCertificate;
        }

        private static bool ValidateCertificate(
            object sender,
            X509Certificate certificate,
            X509Chain chain,
            SslPolicyErrors errors)
        {
            if (errors == SslPolicyErrors.None) return true;
            if ((errors & SslPolicyErrors.RemoteCertificateNameMismatch) != 0) return false;
            if (errors == SslPolicyErrors.RemoteCertificateChainErrors) return true;
            return false;
        }
    }
}
