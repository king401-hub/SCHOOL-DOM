package com.schooldom.schooldom_scanner_kiosk

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

/** Direct port of lib/storage/offline_queue.dart - plain (unencrypted)
 * SharedPreferences, same as the Dart side: this only ever holds scan
 * submissions, nothing session/credential-sensitive. */
object OfflineQueue {
    private const val PREFS_NAME = "schooldom_offline_queue_store"
    private const val KEY_QUEUE = "offline_queue"

    private fun prefs(context: Context) =
        context.applicationContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    fun readQueue(context: Context): List<JSONObject> {
        val raw = prefs(context).getString(KEY_QUEUE, null) ?: return emptyList()
        return try {
            val array = JSONArray(raw)
            (0 until array.length()).map { array.getJSONObject(it) }
        } catch (e: Throwable) {
            emptyList()
        }
    }

    fun writeQueue(context: Context, queue: List<JSONObject>) {
        val array = JSONArray()
        queue.forEach { array.put(it) }
        prefs(context).edit().putString(KEY_QUEUE, array.toString()).apply()
    }

    fun enqueue(context: Context, method: String, endpoint: String, payload: JSONObject?) {
        val queue = readQueue(context).toMutableList()
        val item = JSONObject().apply {
            put("method", method)
            put("endpoint", endpoint)
            put("payload", payload)
            put("queuedAt", isoNow())
        }
        queue.add(item)
        writeQueue(context, queue)
    }

    private fun payloadIdempotencyKey(item: JSONObject): String? {
        val payload = item.optJSONObject("payload") ?: return null
        return if (payload.has("idempotency_key") && !payload.isNull("idempotency_key")) {
            payload.getString("idempotency_key")
        } else {
            null
        }
    }

    /** Drops a just-enqueued scan for a card nothing recognizes offline - it
     * would fail the same way (404) on every future replay attempt, keeping
     * the pending count permanently stuck above zero. */
    fun removeByIdempotencyKey(context: Context, idempotencyKey: String) {
        val queue = readQueue(context).filterNot { payloadIdempotencyKey(it) == idempotencyKey }
        writeQueue(context, queue)
    }

    /** Flags the just-enqueued offline scan so its eventual replay tells the
     * server not to send its own gate SMS (the terminal already texted the
     * parent directly from its own SIM). */
    fun markSmsSentLocally(context: Context, idempotencyKey: String) {
        val queue = readQueue(context)
        queue.forEach { item ->
            if (payloadIdempotencyKey(item) == idempotencyKey) {
                item.optJSONObject("payload")?.put("sms_sent_locally", true)
            }
        }
        writeQueue(context, queue)
    }
}
