using System;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;

namespace SchoolDom.StudentCbt.Win7
{
    public class LanClient
    {
        private const int DiscoveryPort = 4786;
        private const string DiscoveryQuery = "SCHOOLDOM_CBT_DISCOVER";
        public string BaseUrl { get; set; }

        public string Discover()
        {
            using (var udp = new UdpClient())
            {
                udp.EnableBroadcast = true;
                udp.Client.ReceiveTimeout = 3000;
                var query = Encoding.UTF8.GetBytes(DiscoveryQuery);
                udp.Send(query, query.Length, new IPEndPoint(IPAddress.Broadcast, DiscoveryPort));
                var remote = new IPEndPoint(IPAddress.Any, 0);
                var bytes = udp.Receive(ref remote);
                var payload = JsonUtil.Object(Encoding.UTF8.GetString(bytes));
                var urls = JsonUtil.List(payload.ContainsKey("urls") ? payload["urls"] : null);
                if (urls.Count > 0) BaseUrl = JsonUtil.Text(urls[0]).TrimEnd('/');
                if (string.IsNullOrWhiteSpace(BaseUrl)) BaseUrl = "http://" + remote.Address + ":4785";
                return BaseUrl;
            }
        }

        public Dictionary<string, object> Login(string studentId, string pin)
        {
            return Post("/api/login", new Dictionary<string, object> { { "studentId", studentId }, { "pin", pin } });
        }

        public Dictionary<string, object> ExamDetail(string examId)
        {
            return Get("/api/exams/" + Uri.EscapeDataString(examId));
        }

        public Dictionary<string, object> SaveAnswers(string sessionId, Dictionary<string, object> answers)
        {
            return Post("/api/sessions/" + Uri.EscapeDataString(sessionId) + "/answers", new Dictionary<string, object> { { "answers", answers } });
        }

        public Dictionary<string, object> Submit(string sessionId, Dictionary<string, object> answers)
        {
            return Post("/api/sessions/" + Uri.EscapeDataString(sessionId) + "/submit", new Dictionary<string, object> { { "answers", answers } });
        }

        public void FocusLoss(string sessionId)
        {
            Post("/api/sessions/" + Uri.EscapeDataString(sessionId) + "/focus-loss", new Dictionary<string, object> { { "reason", "focus_lost" } });
        }

        private Dictionary<string, object> Get(string path)
        {
            var request = (HttpWebRequest)WebRequest.Create(BaseUrl + path);
            request.Method = "GET";
            request.Timeout = 15000;
            return ReadResponse(request);
        }

        private Dictionary<string, object> Post(string path, object body)
        {
            var request = (HttpWebRequest)WebRequest.Create(BaseUrl + path);
            request.Method = "POST";
            request.Timeout = 15000;
            request.ContentType = "application/json";
            var bytes = Encoding.UTF8.GetBytes(JsonUtil.Serialize(body));
            using (var stream = request.GetRequestStream()) stream.Write(bytes, 0, bytes.Length);
            return ReadResponse(request);
        }

        private static Dictionary<string, object> ReadResponse(HttpWebRequest request)
        {
            try
            {
                using (var response = (HttpWebResponse)request.GetResponse())
                using (var stream = response.GetResponseStream())
                using (var reader = new StreamReader(stream ?? Stream.Null))
                {
                    return JsonUtil.Object(reader.ReadToEnd());
                }
            }
            catch (WebException ex)
            {
                if (ex.Response != null)
                {
                    using (var stream = ex.Response.GetResponseStream())
                    using (var reader = new StreamReader(stream ?? Stream.Null))
                    {
                        throw new InvalidOperationException(reader.ReadToEnd());
                    }
                }
                throw;
            }
        }
    }
}
