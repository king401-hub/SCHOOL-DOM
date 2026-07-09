using System;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;

namespace SchoolDom.StudentCbt.Win7
{
    public class LanClient
    {
        private const int DiscoveryPort = 4786;
        private const string DiscoveryQuery = "SCHOOLDOM_CBT_DISCOVER";
        private const int DefaultTimeout = 15000; // 15 seconds for low-end devices
        private const int DiscoveryTimeout = 5000;
        private static readonly int MaxRetries = 2;
        private static readonly Random Jitter = new Random();
        
        public string BaseUrl { get; set; }
        public int Timeout { get; set; } = DefaultTimeout;
        public bool IsConnected { get; private set; }

        // Optional token supplied by the student (copied from the admin's dashboard)
        public string DiscoveryToken { get; set; }

        public string Discover()
        {
            var localIPs = GetLocalIPs();

            foreach (var localIP in localIPs)
            {
                try
                {
                    var result = DiscoverOnInterface(localIP);
                    if (!string.IsNullOrWhiteSpace(result))
                    {
                        BaseUrl = result.TrimEnd('/');
                        IsConnected = true;
                        return BaseUrl;
                    }
                }
                catch
                {
                    // Try next interface
                }
            }

            throw new InvalidOperationException("No LAN server found. Ask your admin for the network token and enter it below.");
        }

        private List<IPAddress> GetLocalIPs()
        {
            var result = new List<IPAddress>();
            try
            {
                var host = Dns.GetHostEntry(Dns.GetHostName());
                foreach (var ip in host.AddressList)
                {
                    if (ip.AddressFamily == AddressFamily.InterNetwork)
                    {
                        result.Add(ip);
                    }
                }
            }
            catch
            {
                // Fallback - try to get local IPs manually
                foreach (var ip in Dns.GetHostAddresses(Dns.GetHostName()))
                {
                    if (ip.AddressFamily == AddressFamily.InterNetwork)
                    {
                        result.Add(ip);
                    }
                }
            }
            
            // Add loopback as last resort
            if (result.Count == 0) result.Add(IPAddress.Loopback);
            
            return result;
        }

        private string DiscoverOnInterface(IPAddress localIP)
        {
            for (int attempt = 0; attempt <= MaxRetries; attempt++)
            {
                try
                {
                    using (var udp = new UdpClient(new IPEndPoint(localIP, 0)))
                    {
                        udp.EnableBroadcast = true;
                        udp.Client.ReceiveTimeout = DiscoveryTimeout + (attempt * 1000);

                        // Include token if available so the server can authenticate the request
                        var queryText = string.IsNullOrWhiteSpace(DiscoveryToken)
                            ? DiscoveryQuery
                            : DiscoveryQuery + ":" + DiscoveryToken;
                        var query = Encoding.UTF8.GetBytes(queryText);
                        var endpoints = GetBroadcastEndpoints(localIP);
                        
                        foreach (var endpoint in endpoints)
                        {
                            try
                            {
                                udp.Send(query, query.Length, endpoint);
                            }
                            catch
                            {
                                // Try next endpoint
                            }
                        }
                        
                        var remote = new IPEndPoint(IPAddress.Any, 0);
                        var bytes = udp.Receive(ref remote);
                        var payload = JsonUtil.Object(Encoding.UTF8.GetString(bytes));
                        var urls = JsonUtil.List(payload.ContainsKey("urls") ? payload["urls"] : null);
                        
                        if (urls.Count > 0)
                        {
                            var url = JsonUtil.Text(urls[0]);
                            if (!string.IsNullOrWhiteSpace(url)) return url;
                        }
                        
                        // Try the responder's IP as fallback
                        var fallbackUrl = $"http://{remote.Address}:4785";
                        if (IsServerReachable(fallbackUrl)) return fallbackUrl;
                    }
                }
                catch (SocketException)
                {
                    if (attempt == MaxRetries) throw;
                    Thread.Sleep(500 + Jitter.Next(200));
                }
                catch (Exception)
                {
                    if (attempt == MaxRetries) throw;
                    Thread.Sleep(500 + Jitter.Next(200));
                }
            }
            
            return null;
        }

        private List<IPEndPoint> GetBroadcastEndpoints(IPAddress localIP)
        {
            var result = new List<IPEndPoint>
            {
                new IPEndPoint(IPAddress.Broadcast, DiscoveryPort)
            };
            
            try
            {
                var broadcastIP = GetBroadcastAddress(localIP);
                if (broadcastIP != null)
                {
                    result.Add(new IPEndPoint(broadcastIP, DiscoveryPort));
                }
            }
            catch
            {
                // Ignore broadcast calculation errors
            }
            
            return result;
        }

        private IPAddress GetBroadcastAddress(IPAddress ip)
        {
            var ipBytes = ip.GetAddressBytes();
            // Use standard subnet mask for /24 networks (most common)
            var maskBytes = new byte[] { 255, 255, 255, 0 };
            var broadcastBytes = new byte[4];
            
            for (int i = 0; i < 4; i++)
            {
                broadcastBytes[i] = (byte)(ipBytes[i] | ~maskBytes[i]);
            }
            
            return new IPAddress(broadcastBytes);
        }

        private bool IsServerReachable(string baseUrl)
        {
            try
            {
                var request = CreateRequest(baseUrl + "/health");
                request.Method = "HEAD";
                request.Timeout = 2000;
                request.ReadWriteTimeout = 2000;
                using (var response = (HttpWebResponse)request.GetResponse())
                {
                    return response.StatusCode == HttpStatusCode.OK;
                }
            }
            catch
            {
                return false;
            }
        }

        public Dictionary<string, object> Login(string studentId, string pin)
        {
            return PostWithRetry("/api/login", new Dictionary<string, object>
            {
                { "studentId", studentId?.Trim() ?? "" },
                { "pin", pin?.Trim() ?? "" }
            });
        }

        public Dictionary<string, object> StartSession(string studentId, string examId)
        {
            return PostWithRetry("/api/start-session", new Dictionary<string, object>
            {
                { "studentId", studentId?.Trim() ?? "" },
                { "examId", examId?.Trim() ?? "" }
            });
        }

        public Dictionary<string, object> ExamDetail(string examId)
        {
            return GetWithRetry("/api/exams/" + Uri.EscapeDataString(examId ?? ""));
        }

        public Dictionary<string, object> Health()
        {
            return GetWithRetry("/health");
        }

        public Dictionary<string, object> SaveAnswers(string sessionId, Dictionary<string, object> answers)
        {
            if (string.IsNullOrWhiteSpace(sessionId))
                throw new ArgumentException("Session ID is required");
            if (answers == null) answers = new Dictionary<string, object>();
            
            return PostWithRetry("/api/sessions/" + Uri.EscapeDataString(sessionId) + "/answers",
                new Dictionary<string, object> { { "answers", answers } });
        }

        public Dictionary<string, object> Submit(string sessionId, Dictionary<string, object> answers)
        {
            if (string.IsNullOrWhiteSpace(sessionId))
                throw new ArgumentException("Session ID is required");
            if (answers == null) answers = new Dictionary<string, object>();
            
            return PostWithRetry("/api/sessions/" + Uri.EscapeDataString(sessionId) + "/submit",
                new Dictionary<string, object> { { "answers", answers } });
        }

        public void FocusLoss(string sessionId)
        {
            if (string.IsNullOrWhiteSpace(sessionId)) return;
            
            try
            {
                PostWithRetry("/api/sessions/" + Uri.EscapeDataString(sessionId) + "/focus-loss",
                    new Dictionary<string, object> { { "reason", "focus_lost" } });
            }
            catch
            {
                // Focus loss is non-critical
            }
        }

        private Dictionary<string, object> GetWithRetry(string path)
        {
            Exception lastException = null;
            
            for (int attempt = 0; attempt <= MaxRetries; attempt++)
            {
                try
                {
                    return Get(path);
                }
                catch (WebException ex)
                {
                    lastException = ex;
                    if (IsClientError(ex)) throw;
                    if (attempt == MaxRetries) break;
                    WaitForRetry(attempt);
                }
                catch (Exception ex)
                {
                    lastException = ex;
                    if (attempt == MaxRetries) break;
                    WaitForRetry(attempt);
                }
            }
            
            throw lastException ?? new InvalidOperationException("Request failed after retries");
        }

        private Dictionary<string, object> PostWithRetry(string path, object body)
        {
            Exception lastException = null;
            
            for (int attempt = 0; attempt <= MaxRetries; attempt++)
            {
                try
                {
                    return Post(path, body);
                }
                catch (WebException ex)
                {
                    lastException = ex;
                    if (IsClientError(ex)) throw;
                    if (attempt == MaxRetries) break;
                    WaitForRetry(attempt);
                }
                catch (Exception ex)
                {
                    lastException = ex;
                    if (attempt == MaxRetries) break;
                    WaitForRetry(attempt);
                }
            }
            
            throw lastException ?? new InvalidOperationException("Request failed after retries");
        }

        private bool IsClientError(WebException ex)
        {
            if (ex.Response is HttpWebResponse response)
            {
                var statusCode = (int)response.StatusCode;
                return statusCode >= 400 && statusCode < 500;
            }
            return false;
        }

        private void WaitForRetry(int attempt)
        {
            var delay = (int)(Math.Pow(2, attempt) * 1000);
            delay += Jitter.Next(0, 500);
            Thread.Sleep(delay);
        }

        private Dictionary<string, object> Get(string path)
        {
            if (string.IsNullOrWhiteSpace(BaseUrl))
                throw new InvalidOperationException("Base URL not set. Call Discover() first.");
            
            var request = CreateRequest(BaseUrl + path);
            request.Method = "GET";
           return ReadResponse(request);
        }

        private Dictionary<string, object> Post(string path, object body)
        {
            if (string.IsNullOrWhiteSpace(BaseUrl))
                throw new InvalidOperationException("Base URL not set. Call Discover() first.");
            
            var request = CreateRequest(BaseUrl + path);
            request.Method = "POST";
           request.ContentType = "application/json";
            
            var json = JsonUtil.Serialize(body);
            var bytes = Encoding.UTF8.GetBytes(json);
            request.ContentLength = bytes.Length;
            
            using (var stream = request.GetRequestStream())
            {
                stream.Write(bytes, 0, bytes.Length);
                stream.Flush();
            }
            
            return ReadResponse(request);
        }

        private HttpWebRequest CreateRequest(string url)
        {
            var request = (HttpWebRequest)WebRequest.Create(url);
            
            // Windows 7 compatible settings
            request.Timeout = Timeout;
            request.ReadWriteTimeout = Timeout;
            request.KeepAlive = false;
            request.ProtocolVersion = HttpVersion.Version10;
            request.AllowAutoRedirect = false;
            request.UserAgent = "SchoolDom-Student-CBT/1.0 (Windows 7)";
            request.Accept = "application/json";
            
            // Tls12 (3072) and Tls11 (768) are not named in the .NET 4.0 enum,
            // so we use numeric casts to avoid a compile error on .NET 4.0 targets.
            // The student app only talks HTTP over LAN so TLS is irrelevant here,
            // but we keep the opt-in in case the admin URL is ever HTTPS.
            try
            {
                ServicePointManager.SecurityProtocol = (SecurityProtocolType)3072 |  // TLS 1.2
                                                       (SecurityProtocolType)768  |  // TLS 1.1
                                                       SecurityProtocolType.Tls;
            }
            catch
            {
                try { ServicePointManager.SecurityProtocol = SecurityProtocolType.Tls; }
                catch { /* Ignore - Win7 RTM only has TLS 1.0 by default */ }
            }
            
            return request;
        }

        private static Dictionary<string, object> ReadResponse(HttpWebRequest request)
        {
            try
            {
                using (var response = (HttpWebResponse)request.GetResponse())
                using (var stream = response.GetResponseStream())
                {
                    if (stream == null) return new Dictionary<string, object>();
                    
                    using (var reader = new StreamReader(stream, Encoding.UTF8))
                    {
                        var content = reader.ReadToEnd();
                        var result = JsonUtil.Object(content);
                        IsConnected = true;
                        return result;
                    }
                }
            }
            catch (WebException ex)
            {
                IsConnected = false;
                if (ex.Response != null)
                {
                    using (var stream = ex.Response.GetResponseStream())
                    using (var reader = new StreamReader(stream ?? Stream.Null, Encoding.UTF8))
                    {
                        var errorContent = reader.ReadToEnd();
                        try
                        {
                            var errorObj = JsonUtil.Object(errorContent);
                            var message = errorObj.ContainsKey("message") ? 
                                JsonUtil.Text(errorObj["message"]) : errorContent;
                            throw new InvalidOperationException(message);
                        }
                        catch
                        {
                            throw new InvalidOperationException(errorContent);
                        }
                    }
                }
                throw;
            }
        }
    }
}
