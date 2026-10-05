package com.schooldom.schooldom_scanner_kiosk

import android.content.Context
import android.util.Log
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
 * Direct port of lib/api/client.dart's apiRequest/postJson/getJson/
 * replayOfflineQueue, using plain HttpURLConnection instead of the `http`
 * package (no network access on this machine to fetch OkHttp or anything
 * else - see app/build.gradle.kts). Every method here is BLOCKING - callers
 * must run it off the main thread (see TopwisePrinterBridge's
 * Executors.newSingleThreadExecutor() pattern for the convention this app
 * uses elsewhere).
 */
class ApiException(message: String, val statusCode: Int? = null) : Exception(message)
class SessionExpiredException : Exception()

data class ReplayResult(val synced: Int, val remaining: Int, val sessionExpired: Boolean)

object ApiClient {
    // Bounds each queued item's sync attempt during a replay pass - same
    // reasoning as the Dart side's _replayItemTimeout: a flaky-but-not-fully-
    // down connection must not hang a replay pass indefinitely.
    private const val REPLAY_ITEM_TIMEOUT_MS = 10_000L

    @Volatile private var replayInProgress = false
    @Volatile private var appContext: Context? = null

    /** Must be called once before any network call (see MainActivity.onCreate) -
     * needed to load the bundled TLS trust anchor (see TlsConfig). */
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

    /** Raw send - no auth, no retry, no queueing. Returns (statusCode, body). */
    private fun send(method: String, urlStr: String, headers: Map<String, String>, body: String?, timeoutMs: Int): Pair<Int, String> {
        val tag = "ApiClientTrace"
        Log.d(tag, "send: start $method $urlStr")
        val connection = URL(urlStr).openConnection() as HttpURLConnection
        Log.d(tag, "send: connection opened")
        if (connection is HttpsURLConnection) {
            appContext?.let {
                Log.d(tag, "send: building TLS socket factory")
                connection.sslSocketFactory = TlsConfig.socketFactory(it)
                Log.d(tag, "send: TLS socket factory set")
            }
        }
        try {
            connection.requestMethod = method
            connection.connectTimeout = timeoutMs
            connection.readTimeout = timeoutMs
            connection.setRequestProperty("Connection", "close")
            headers.forEach { (k, v) -> connection.setRequestProperty(k, v) }
            if (body != null) {
                Log.d(tag, "send: writing body (${body.length} chars)")
                connection.doOutput = true
                OutputStreamWriter(connection.outputStream, Charsets.UTF_8).use { it.write(body) }
                Log.d(tag, "send: body written")
            }
            Log.d(tag, "send: requesting responseCode")
            val status = connection.responseCode
            Log.d(tag, "send: got responseCode=$status, contentLength=${connection.contentLength}, headers=${connection.headerFields}")
            val stream = if (status in 200..299) connection.inputStream else connection.errorStream
            val contentLength = connection.contentLength
            val responseBody = stream?.let {
                if (contentLength >= 0) {
                    val buffer = ByteArray(contentLength)
                    var read = 0
                    while (read < contentLength) {
                        val n = it.read(buffer, read, contentLength - read)
                        Log.d(tag, "send: read chunk n=$n, total=$read/$contentLength")
                        if (n < 0) break
                        read += n
                    }
                    String(buffer, 0, read, Charsets.UTF_8)
                } else {
                    BufferedReader(InputStreamReader(it, Charsets.UTF_8)).use { reader -> reader.readText() }
                }
            } ?: ""
            Log.d(tag, "send: done, body=$responseBody")
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
            put("signedInAt", isoNow())
        }
        SessionStore.saveSession(context, next)
        return next
    }

    /**
     * @param timeoutMs One overall budget for the whole call (first attempt,
     * any token refresh, and the retry) - running out is treated like having
     * no network when [queueWhenOffline] is set.
     */
    fun apiRequest(
        context: Context,
        method: String,
        endpoint: String,
        payload: JSONObject? = null,
        retry: Boolean = true,
        queueWhenOffline: Boolean = false,
        timeoutMs: Long? = null,
    ): JSONObject {
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

        val deadline = timeoutMs?.let { System.currentTimeMillis() + it }
        fun budgetMs(): Int {
            if (deadline == null) return 30_000 // sane default connect/read timeout when no overall budget given
            val left = deadline - System.currentTimeMillis()
            return if (left < 0) 0 else left.toInt()
        }

        fun saveForLater(timedOut: Boolean): JSONObject {
            OfflineQueue.enqueue(context, method, endpoint, payload)
            return JSONObject().apply {
                put("success", true)
                put("offline", true)
                if (timedOut) put("timed_out", true)
                put("message", "Saved offline.")
            }
        }

        var statusCode: Int
        var responseBody: String
        try {
            val (s, b) = send(method, url, headers, body, budgetMs())
            statusCode = s; responseBody = b
        } catch (e: SocketTimeoutException) {
            if (queueWhenOffline && method != "GET") return saveForLater(timedOut = true)
            throw ApiException("The server took too long to respond.")
        } catch (e: IOException) {
            if (queueWhenOffline && method != "GET") return saveForLater(timedOut = false)
            throw ApiException("Network error. Check your connection.")
        }

        if (statusCode == 401 && retry) {
            try {
                session = tryRefresh(context, session, budgetMs())
                headers["Authorization"] = "Bearer ${session.getString("access")}"
                val (s, b) = send(method, url, headers, body, budgetMs())
                statusCode = s; responseBody = b
            } catch (e: SocketTimeoutException) {
                if (queueWhenOffline && method != "GET") return saveForLater(timedOut = true)
                throw ApiException("The server took too long to respond.")
            } catch (e: IOException) {
                if (queueWhenOffline && method != "GET") return saveForLater(timedOut = false)
                throw ApiException("Network error. Check your connection.")
            }
        }

        val data = if (responseBody.isNotEmpty()) JSONObject(responseBody) else JSONObject()

        if (statusCode in 200..299) return data

        if (statusCode == 401) {
            SessionStore.clearSession(context)
            throw SessionExpiredException()
        }

        throw ApiException(parseError(data, "Request failed ($statusCode)."), statusCode)
    }

    fun postJson(context: Context, endpoint: String, payload: JSONObject, queueWhenOffline: Boolean = false, timeoutMs: Long? = null): JSONObject =
        apiRequest(context, "POST", endpoint, payload = payload, queueWhenOffline = queueWhenOffline, timeoutMs = timeoutMs)

    fun getJson(context: Context, endpoint: String): JSONObject =
        apiRequest(context, "GET", endpoint)

    /** Unauthenticated POST - for provisioning, which happens before any
     * session exists, so apiRequest's "must already have an access token"
     * check doesn't apply yet. */
    fun rawPost(path: String, body: JSONObject, timeoutMs: Int = 15_000): Pair<Int, String> =
        send("POST", "${Config.API_BASE_URL}$path", mapOf("Content-Type" to "application/json"), body.toString(), timeoutMs)

    /** Mirrors replayOfflineQueue in client.dart exactly, including the
     * same guard against overlapping concurrent passes and the same
     * short-circuit on SessionExpiredException (every remaining item would
     * fail the exact same way - leave them all queued rather than burn
     * through the rest one doomed call at a time). */
    fun replayOfflineQueue(context: Context): ReplayResult {
        if (replayInProgress) {
            return ReplayResult(synced = 0, remaining = OfflineQueue.readQueue(context).size, sessionExpired = false)
        }
        replayInProgress = true
        try {
            val queue = OfflineQueue.readQueue(context)
            if (queue.isEmpty()) return ReplayResult(0, 0, sessionExpired = false)

            val failed = mutableListOf<JSONObject>()
            var synced = 0
            for (index in queue.indices) {
                val item = queue[index]
                try {
                    apiRequest(
                        context,
                        item.getString("method"),
                        item.getString("endpoint"),
                        payload = item.optJSONObject("payload"),
                        queueWhenOffline = false,
                        timeoutMs = REPLAY_ITEM_TIMEOUT_MS,
                    )
                    synced++
                } catch (e: SessionExpiredException) {
                    failed.addAll(queue.subList(index, queue.size))
                    OfflineQueue.writeQueue(context, failed)
                    return ReplayResult(synced, failed.size, sessionExpired = true)
                } catch (e: Exception) {
                    failed.add(item)
                }
            }
            OfflineQueue.writeQueue(context, failed)
            return ReplayResult(synced, failed.size, sessionExpired = false)
        } finally {
            replayInProgress = false
        }
    }
}
