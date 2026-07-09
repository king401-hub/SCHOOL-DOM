using System;
using System.Collections.Generic;
using System.Text;
using System.Web.Script.Serialization;

namespace SchoolDom.StudentCbt.Win7
{
    public static class JsonUtil
    {
        // Reuse the same serializer instance (thread-safe in .NET 4+)
        private static readonly JavaScriptSerializer Serializer = new JavaScriptSerializer
        {
            MaxJsonLength = int.MaxValue,
            RecursionLimit = 100 // Prevent stack overflow on deeply nested JSON
        };

        // Cache for frequently used empty objects to reduce allocations
        private static readonly Dictionary<string, object> EmptyObject = new Dictionary<string, object>();
        private static readonly List<object> EmptyList = new List<object>();

        /// <summary>
        /// Serializes an object to JSON string
        /// </summary>
        public static string Serialize(object value)
        {
            if (value == null) return "null";
            
            try
            {
                return Serializer.Serialize(value);
            }
            catch (Exception ex)
            {
                // Fallback for serialization errors
                return $"{{\"error\":\"Serialization failed: {ex.Message}\"}}";
            }
        }

        /// <summary>
        /// Deserializes JSON string to Dictionary
        /// </summary>
        public static Dictionary<string, object> Object(string json)
        {
            if (string.IsNullOrWhiteSpace(json)) 
                return EmptyObject;

            try
            {
                var result = Serializer.DeserializeObject(json) as Dictionary<string, object>;
                return result ?? EmptyObject;
            }
            catch (Exception)
            {
                // Return empty on parse failure (silent fail for robustness)
                return EmptyObject;
            }
        }

        /// <summary>
        /// Safely converts any object to string
        /// </summary>
        public static string Text(object value)
        {
            if (value == null) return "";
            
            // Fast path for common types
            if (value is string str) return str;
            if (value is int i) return i.ToString();
            if (value is long l) return l.ToString();
            if (value is double d) return d.ToString(System.Globalization.CultureInfo.InvariantCulture);
            if (value is bool b) return b ? "true" : "false";
            if (value is DateTime dt) return dt.ToString("yyyy-MM-ddTHH:mm:ss.fffZ");
            if (value is decimal dec) return dec.ToString(System.Globalization.CultureInfo.InvariantCulture);
            
            // Fallback
            return Convert.ToString(value) ?? "";
        }

        /// <summary>
        /// Safely converts any object to int with fallback
        /// </summary>
        public static int Int(object value, int fallback = 0)
        {
            if (value == null) return fallback;

            // Fast path for common numeric types
            if (value is int i) return i;
            if (value is long l) return (int)l;
            if (value is double d) return (int)d;
            if (value is short s) return s;
            if (value is byte b) return b;
            if (value is decimal dec) return (int)dec;
            
            // String parsing (only when needed)
            if (value is string str)
            {
                // Trim and try parse
                str = str.Trim();
                if (string.IsNullOrEmpty(str)) return fallback;
                
                if (int.TryParse(str, System.Globalization.NumberStyles.Integer, 
                    System.Globalization.CultureInfo.InvariantCulture, out int parsed))
                {
                    return parsed;
                }
            }
            
            return fallback;
        }

        /// <summary>
        /// Safely converts any object to long with fallback
        /// </summary>
        public static long Long(object value, long fallback = 0)
        {
            if (value == null) return fallback;

            if (value is long l) return l;
            if (value is int i) return i;
            if (value is double d) return (long)d;
            if (value is short s) return s;
            if (value is byte b) return b;
            if (value is decimal dec) return (long)dec;
            
            if (value is string str)
            {
                str = str.Trim();
                if (string.IsNullOrEmpty(str)) return fallback;
                
                if (long.TryParse(str, System.Globalization.NumberStyles.Integer, 
                    System.Globalization.CultureInfo.InvariantCulture, out long parsed))
                {
                    return parsed;
                }
            }
            
            return fallback;
        }

        /// <summary>
        /// Safely converts any object to double with fallback
        /// </summary>
        public static double Double(object value, double fallback = 0.0)
        {
            if (value == null) return fallback;

            if (value is double d) return d;
            if (value is int i) return i;
            if (value is long l) return l;
            if (value is float f) return f;
            if (value is decimal dec) return (double)dec;
            
            if (value is string str)
            {
                str = str.Trim();
                if (string.IsNullOrEmpty(str)) return fallback;
                
                if (double.TryParse(str, System.Globalization.NumberStyles.Float, 
                    System.Globalization.CultureInfo.InvariantCulture, out double parsed))
                {
                    return parsed;
                }
            }
            
            return fallback;
        }

        /// <summary>
        /// Safely converts any object to bool with fallback
        /// </summary>
        public static bool Bool(object value, bool fallback = false)
        {
            if (value == null) return fallback;

            if (value is bool b) return b;
            if (value is int i) return i != 0;
            if (value is long l) return l != 0;
            
            if (value is string str)
            {
                str = str.Trim().ToLowerInvariant();
                if (str == "true" || str == "1" || str == "yes" || str == "y") return true;
                if (str == "false" || str == "0" || str == "no" || str == "n") return false;
            }
            
            return fallback;
        }

        /// <summary>
        /// Safely converts any object to DateTime with fallback
        /// </summary>
        public static DateTime DateTime(object value, DateTime? fallback = null)
        {
            if (value == null) return fallback ?? System.DateTime.MinValue;

            if (value is DateTime dt) return dt;
            if (value is DateTimeOffset dto) return dto.UtcDateTime;
            
            if (value is string str)
            {
                str = str.Trim();
                if (string.IsNullOrEmpty(str)) return fallback ?? System.DateTime.MinValue;
                
                if (System.DateTime.TryParse(str, System.Globalization.CultureInfo.InvariantCulture, 
                    System.Globalization.DateTimeStyles.RoundtripKind, out System.DateTime parsed))
                {
                    return parsed;
                }
            }
            
            return fallback ?? System.DateTime.MinValue;
        }

        /// <summary>
        /// Safely converts any object to List of objects
        /// </summary>
        public static List<object> List(object value)
        {
            if (value == null) return EmptyList;

            // Already a list
            if (value is List<object> list) return list;
            
            // Array
            if (value is object[] array)
            {
                // Reuse if empty
                if (array.Length == 0) return EmptyList;
                return new List<object>(array);
            }
            
            // Dictionary (treat as single item list)
            if (value is Dictionary<string, object>)
            {
                return new List<object> { value };
            }
            
            // String (treat as single item list)
            if (value is string)
            {
                return new List<object> { value };
            }
            
            // Try to enumerate
            if (value is System.Collections.IEnumerable enumerable && !(value is string))
            {
                var result = new List<object>();
                try
                {
                    foreach (var item in enumerable)
                    {
                        result.Add(item);
                    }
                }
                catch
                {
                    // Enumeration failed
                }
                return result;
            }
            
            return EmptyList;
        }

        /// <summary>
        /// Safely gets a value from a dictionary with fallback
        /// </summary>
        public static T Get<T>(Dictionary<string, object> dict, string key, T fallback = default(T))
        {
            if (dict == null || string.IsNullOrEmpty(key)) return fallback;
            
            if (dict.TryGetValue(key, out object value))
            {
                try
                {
                    return (T)Convert.ChangeType(value, typeof(T), 
                        System.Globalization.CultureInfo.InvariantCulture);
                }
                catch
                {
                    // Conversion failed
                }
            }
            
            return fallback;
        }

        /// <summary>
        /// Creates a new dictionary with proper capacity for performance
        /// </summary>
        public static Dictionary<string, object> NewDictionary(int capacity = 4)
        {
            return new Dictionary<string, object>(capacity);
        }

        /// <summary>
        /// Creates a new list with proper capacity for performance
        /// </summary>
        public static List<object> NewList(int capacity = 4)
        {
            return new List<object>(capacity);
        }

        /// <summary>
        /// Checks if a JSON string is valid
        /// </summary>
        public static bool IsValidJson(string json)
        {
            if (string.IsNullOrWhiteSpace(json)) return false;
            
            try
            {
                Serializer.DeserializeObject(json);
                return true;
            }
            catch
            {
                return false;
            }
        }

        /// <summary>
        /// Pretty prints a JSON string for debugging
        /// </summary>
        public static string PrettyPrint(string json)
        {
            if (string.IsNullOrWhiteSpace(json)) return json;
            
            try
            {
                var obj = Serializer.DeserializeObject(json);
                return Serializer.Serialize(obj);
            }
            catch
            {
                return json;
            }
        }
    }
}