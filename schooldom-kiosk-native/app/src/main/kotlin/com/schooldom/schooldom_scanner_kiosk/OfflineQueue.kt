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
}
