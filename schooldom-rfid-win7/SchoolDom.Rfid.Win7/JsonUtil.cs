using System;
using System.Collections.Generic;
using System.Security.Cryptography;
using System.Text;
using System.Web.Script.Serialization;

namespace SchoolDom.Rfid.Win7
{
    // Ported from SchoolDom.Cbt.Win7 - JavaScriptSerializer (System.Web.Extensions) is
    // the JSON approach used across the SchoolDom Win7 app family instead of a
    // third-party package, keeping this app's dependency list at zero too.
    public static class JsonUtil
    {
        private static readonly JavaScriptSerializer Serializer = new JavaScriptSerializer { MaxJsonLength = int.MaxValue };

        public static string Serialize(object value)
        {
            return Serializer.Serialize(value);
        }

        public static T Deserialize<T>(string json)
        {
            return Serializer.Deserialize<T>(json);
        }

        public static Dictionary<string, object> DeserializeObject(string json)
        {
            return Serializer.DeserializeObject(json) as Dictionary<string, object> ?? new Dictionary<string, object>();
        }

        public static string Sha256(string value)
        {
            using (var sha = SHA256.Create())
            {
                var bytes = sha.ComputeHash(Encoding.UTF8.GetBytes(value ?? ""));
                var builder = new StringBuilder(bytes.Length * 2);
                foreach (var b in bytes) builder.Append(b.ToString("x2"));
                return builder.ToString();
            }
        }

        public static string IsoNow()
        {
            return DateTime.UtcNow.ToString("o");
        }

        public static string Text(object value, string fallback = "")
        {
            return value == null ? fallback : Convert.ToString(value);
        }

        public static int Int(object value, int fallback = 0)
        {
            if (value == null) return fallback;
            int parsed;
            return int.TryParse(Convert.ToString(value), out parsed) ? parsed : fallback;
        }
    }
}
