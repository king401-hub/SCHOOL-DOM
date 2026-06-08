using System;
using System.Collections.Generic;
using System.Web.Script.Serialization;

namespace SchoolDom.StudentCbt.Win7
{
    public static class JsonUtil
    {
        private static readonly JavaScriptSerializer Serializer = new JavaScriptSerializer { MaxJsonLength = int.MaxValue };
        public static string Serialize(object value) { return Serializer.Serialize(value); }
        public static Dictionary<string, object> Object(string json) { return Serializer.DeserializeObject(json) as Dictionary<string, object> ?? new Dictionary<string, object>(); }
        public static string Text(object value) { return value == null ? "" : Convert.ToString(value); }
        public static int Int(object value, int fallback) { int parsed; return int.TryParse(Text(value), out parsed) ? parsed : fallback; }
        public static List<object> List(object value)
        {
            var arr = value as object[];
            return arr == null ? new List<object>() : new List<object>(arr);
        }
    }
}

