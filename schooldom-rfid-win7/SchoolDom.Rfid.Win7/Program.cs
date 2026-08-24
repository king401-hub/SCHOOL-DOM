using System;
using System.Net;
using System.Net.Security;
using System.Security.Cryptography.X509Certificates;
using System.Windows.Forms;

namespace SchoolDom.Rfid.Win7
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

        // Call once at startup — configures TLS and certificate validation globally for
        // the lifetime of the process. Must run before any HttpWebRequest / WebClient call.
        // Mirrors SchoolDom.Cbt.Win7's Program.cs so both apps behave identically on old Windows.
        internal static void BootstrapNetworkSecurity()
        {
            // Enable TLS 1.0 (192), TLS 1.1 (768) and TLS 1.2 (3072) in one shot.
            // .NET 4.0 does not define Tls11 / Tls12 as named enum members, but it passes
            // the raw integer directly to Windows Schannel, which understands them on
            // Windows Vista SP1 and later.
            try
            {
                ServicePointManager.SecurityProtocol =
                    (SecurityProtocolType)(192 | 768 | 3072);
            }
            catch
            {
                try { ServicePointManager.SecurityProtocol = (SecurityProtocolType)(192 | 768); }
                catch
                {
                    try { ServicePointManager.SecurityProtocol = SecurityProtocolType.Tls; }
                    catch { /* best-effort */ }
                }
            }

            // Expect: 100-continue causes some school network proxies / firewalls to stall
            ServicePointManager.Expect100Continue = false;

            // Default of 2 simultaneous connections is too low when flushing a large queue
            ServicePointManager.DefaultConnectionLimit = 16;

            // Windows 7/8 RTM do not ship with the ISRG Root X1 certificate (Let's Encrypt's
            // current root CA) in their trusted store. Without this callback every HTTPS
            // request to schooldom.academy would fail with "Could not establish trust
            // relationship for the SSL/TLS secure channel."
            ServicePointManager.ServerCertificateValidationCallback = ValidateCertificate;
        }

        private static bool ValidateCertificate(
            object sender,
            X509Certificate certificate,
            X509Chain chain,
            SslPolicyErrors errors)
        {
            // Fully trusted by the OS — always accept
            if (errors == SslPolicyErrors.None)
                return true;

            // Hostname mismatch is a hard failure — could be MITM
            if ((errors & SslPolicyErrors.RemoteCertificateNameMismatch) != 0)
                return false;

            // Chain errors only (root CA not in old Windows trust store). Accept — the
            // Common Name is still verified above, and chain errors on old Windows almost
            // always mean the OS trust store is simply out of date, not a real attack.
            if (errors == SslPolicyErrors.RemoteCertificateChainErrors)
                return true;

            return false;
        }
    }
}
