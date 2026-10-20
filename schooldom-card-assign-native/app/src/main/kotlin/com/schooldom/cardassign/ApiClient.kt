package com.schooldom.cardassign

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.io.IOException
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.SocketTimeoutException
import java.net.URL
import javax.net.ssl.HttpsURLConnection

/**
 * Trimmed port of schooldom-kiosk-native's ApiClient - same HttpURLConnection
 * + TLS-pinning + refresh-on-401 approach (this app runs on the exact same
 * old-firmware terminals that needed TlsConfig's TLS 1.2 workaround), minus
 * the offline queue: a card assignment that can't reach the server right now
 * should just fail with a clear error, not silently queue - nothing here is
 * time-sensitive the way a gate attendance scan is.
 */
class ApiException(message: String, val statusCode: Int? = null) : Exception(message)
class SessionExpiredException : Exception()

object ApiClient {
    @Volatile private var appContext: Context? = null

    /** Must be called once before any network call (see MainActivity.onCreate). */
    fun init(context: Context) {
        appContext = context.applicationContext
    }

    private fun parseError(data: JSONObject?, fallback: String): String {
        if (data == null) return fallback
        for (k in listOf("message", "detail", "error")) {
            if (data.has(k) && !data.isNull(k)) return data.getString(k)
        }
        val keys = data.keys()
        if (keys.hasNext()) {
            val first = keys.next()
            val v = data.get(first)
            val text = if (v is JSONArray && v.length() > 0) v.get(0).toString() else v.toString()
            return "$first: $text"
        }
        return fallback
    }

    private fun send(method: String, urlStr: String, headers: Map<String, String>, body: String?, timeoutMs: Int): Pair<Int, String> {
        val connection = URL(urlStr).openConnection() as HttpURLConnection
        if (connection is HttpsURLConnection) {
            appContext?.let { connection.sslSocketFactory = TlsConfig.socketFactory(it) }
        }
        try {
            connection.requestMethod = method
            connection.connectTimeout = timeoutMs
            connection.readTimeout = timeoutMs
            connection.setRequestProperty("Connection", "close")
            headers.forEach { (k, v) -> connection.setRequestProperty(k, v) }
            if (body != null) {
                connection.doOutput = true
                OutputStreamWriter(connection.outputStream, Charsets.UTF_8).use { it.write(body) }
            }
            val status = connection.responseCode
            val stream = if (status in 200..299) connection.inputStream else connection.errorStream
            val contentLength = connection.contentLength
            val responseBody = stream?.let {
                if (contentLength >= 0) {
                    val buffer = ByteArray(contentLength)
                    var read = 0
                    while (read < contentLength) {
                        val n = it.read(buffer, read, contentLength - read)
                        if (n < 0) break
                        read += n
                    }
                    String(buffer, 0, read, Charsets.UTF_8)
                } else {
                    BufferedReader(InputStreamReader(it, Charsets.UTF_8)).use { reader -> reader.readText() }
                }
            } ?: ""
            return status to responseBody
        } finally {
            connection.disconnect()
        }
    }

    private fun tryRefresh(context: Context, session: JSONObject, timeoutMs: Int): JSONObject {
        val refresh = session.optString("refresh", "")
        if (refresh.isEmpty()) {
            SessionStore.clearSession(context)
            throw SessionExpiredException()
        }
        val (status, body) = try {
            send(
                "POST", "${Config.API_BASE_URL}/api/auth/refresh/",
                mapOf("Content-Type" to "application/json"),
                JSONObject().put("refresh", refresh).toString(),
                timeoutMs,
            )
        } catch (e: IOException) {
            SessionStore.clearSession(context)
            throw SessionExpiredException()
        }
        val data = if (body.isNotEmpty()) JSONObject(body) else null
        if (status != 200 || data?.optString("access", "")?.isEmpty() != false) {
            SessionStore.clearSession(context)
            throw SessionExpiredException()
        }
        val next = JSONObject(session.toString()).apply {
            put("access", data.getString("access"))
            if (data.has("refresh")) put("refresh", data.getString("refresh"))
        }
        SessionStore.saveSession(context, next)
        return next
    }

    /** Core request path - returns the status code alongside the parsed
     * body instead of throwing on a non-2xx, so a caller that needs the
     * body of an error response (e.g. card-assignment's 409 conflict
     * payload) can still get at it. */
    fun apiRequestRaw(
        context: Context,
        method: String,
        endpoint: String,
        payload: JSONObject? = null,
        retry: Boolean = true,
        timeoutMs: Long = 15_000L,
    ): Pair<Int, JSONObject> {
        var session = SessionStore.getSession(context)
        if (session == null || session.optString("access", "").isEmpty()) {
            SessionStore.clearSession(context)
            throw SessionExpiredException()
        }

        val url = "${Config.API_BASE_URL}$endpoint"
        val headers = mutableMapOf("Authorization" to "Bearer ${session.getString("access")}")
        val body = payload?.let {
            headers["Content-Type"] = "application/json"
            it.toString()
        }

        var statusCode: Int
        var responseBody: String
        try {
            val (s, b) = send(method, url, headers, body, timeoutMs.toInt())
            statusCode = s; responseBody = b
        } catch (e: SocketTimeoutException) {
            throw ApiException("The server took too long to respond.")
        } catch (e: IOException) {
            throw ApiException("Network error. Check your connection.")
        }

        if (statusCode == 401 && retry) {
            try {
                session = tryRefresh(context, session, timeoutMs.toInt())
                headers["Authorization"] = "Bearer ${session.getString("access")}"
                val (s, b) = send(method, url, headers, body, timeoutMs.toInt())
                statusCode = s; responseBody = b
            } catch (e: SocketTimeoutException) {
                throw ApiException("The server took too long to respond.")
            } catch (e: IOException) {
                throw ApiException("Network error. Check your connection.")
            }
        }

        val data = if (responseBody.isNotEmpty()) JSONObject(responseBody) else JSONObject()

        if (statusCode == 401) {
            SessionStore.clearSession(context)
            throw SessionExpiredException()
        }

        return statusCode to data
    }

    fun apiRequest(
        context: Context,
        method: String,
        endpoint: String,
        payload: JSONObject? = null,
        retry: Boolean = true,
        timeoutMs: Long = 15_000L,
    ): JSONObject {
        val (statusCode, data) = apiRequestRaw(context, method, endpoint, payload, retry, timeoutMs)
        if (statusCode in 200..299) return data
        throw ApiException(parseError(data, "Request failed ($statusCode)."), statusCode)
    }

    fun postJson(context: Context, endpoint: String, payload: JSONObject, timeoutMs: Long = 15_000L): JSONObject =
        apiRequest(context, "POST", endpoint, payload = payload, timeoutMs = timeoutMs)

    fun getJson(context: Context, endpoint: String): JSONObject =
        apiRequest(context, "GET", endpoint)

    /** For calls that need to inspect an error response's body (e.g. the
     * card-assignment conflict payload) rather than just its message. */
    fun postJsonRaw(context: Context, endpoint: String, payload: JSONObject, timeoutMs: Long = 15_000L): Pair<Int, JSONObject> =
        apiRequestRaw(context, "POST", endpoint, payload = payload, timeoutMs = timeoutMs)

    /** Unauthenticated POST - for login, which happens before any session
     * exists, so apiRequest's "must already have an access token" check
     * doesn't apply yet. */
    fun rawPost(path: String, body: JSONObject, timeoutMs: Int = 15_000): Pair<Int, String> =
        send("POST", "${Config.API_BASE_URL}$path", mapOf("Content-Type" to "application/json"), body.toString(), timeoutMs)
}
