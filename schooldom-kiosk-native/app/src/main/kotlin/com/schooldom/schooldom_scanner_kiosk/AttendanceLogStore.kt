package com.schooldom.schooldom_scanner_kiosk

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * A same-day, on-device record of successful scans (clock-in/clock-out),
 * shown in Settings' "Today's Attendance Log" so an admin can glance at who
 * has been scanned without opening the web dashboard. Plain (unencrypted)
 * SharedPreferences, same reasoning as OfflineQueue/GateSettingsCache -
 * nothing credential-sensitive here, just names and times.
 *
 * Intentionally NOT a history: every read/write first checks the stored
 * date against today, and wipes the whole log the moment it finds an older
 * one - a kiosk showing yesterday's (or last week's) names would be a
 * growing, stale, eventually-privacy-awkward list nobody asked for. "Log for
 * that day" is read literally - today only, cleared once the day turns over.
 */
object AttendanceLogStore {
    private const val PREFS_NAME = "schooldom_attendance_log_store"
    private const val KEY_DATE = "log_date"
    private const val KEY_ENTRIES = "log_entries"

    private fun prefs(context: Context) =
        context.applicationContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    private fun today(): String = SimpleDateFormat("yyyy-MM-dd", Locale.US).format(Date())

    private fun rolloverIfNeeded(context: Context) {
        val p = prefs(context)
        if (p.getString(KEY_DATE, null) != today()) {
            p.edit().putString(KEY_DATE, today()).putString(KEY_ENTRIES, "[]").apply()
        }
    }

    fun record(context: Context, name: String, detail: String, outcome: String) {
        rolloverIfNeeded(context)
        val p = prefs(context)
        val array = try {
            JSONArray(p.getString(KEY_ENTRIES, "[]"))
        } catch (e: Throwable) {
            JSONArray()
        }
        array.put(
            JSONObject().apply {
                put("name", name)
                put("detail", detail)
                put("outcome", outcome)
                put("time", SimpleDateFormat("h:mm a", Locale.US).format(Date()))
                put("at", System.currentTimeMillis())
            },
        )
        p.edit().putString(KEY_ENTRIES, array.toString()).apply()
    }

    /** Newest first. Also triggers the day-rollover check, so opening the
     * log screen on a new day shows it already empty rather than stale. */
    fun readToday(context: Context): List<JSONObject> {
        rolloverIfNeeded(context)
        val array = try {
            JSONArray(prefs(context).getString(KEY_ENTRIES, "[]"))
        } catch (e: Throwable) {
            JSONArray()
        }
        return (0 until array.length())
            .map { array.getJSONObject(it) }
            .sortedByDescending { it.optLong("at") }
    }

    fun clear(context: Context) {
        prefs(context).edit().putString(KEY_ENTRIES, "[]").apply()
    }
}
