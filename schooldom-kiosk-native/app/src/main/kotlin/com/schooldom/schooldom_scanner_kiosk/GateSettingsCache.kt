package com.schooldom.schooldom_scanner_kiosk

import android.content.Context
import org.json.JSONObject
import java.util.Calendar

/**
 * Direct port of lib/storage/gate_settings_cache.dart: a local mirror of
 * GateSettings' configured early/late/clock-out time windows
 * (rfid_attendance.models.GateSettings.classify_event), so the kiosk can
 * label an attendance event by time-of-day even with no network to ask the
 * server - see ScanHandler's offline branch. Direction (clock-in vs
 * clock-out) still can't be determined offline (that depends on whether the
 * student already clocked in today, which needs server-side attendance
 * history this client doesn't keep), so this only classifies the time
 * window itself, same as the server does before it separately decides
 * direction. Plain (unencrypted) SharedPreferences, same as the Dart side -
 * nothing credential-sensitive here.
 */
object GateSettingsCache {
    private const val PREFS_NAME = "schooldom_gate_settings_store"
    private const val KEY = "gate_settings_cache"

    private fun prefs(context: Context) =
        context.applicationContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    /** Call with whatever GateEndpoints.loadGateSettings already returned at
     * some other call site - deliberately not fetching its own copy here. */
    fun save(context: Context, data: JSONObject) {
        prefs(context).edit().putString(KEY, data.toString()).apply()
    }

    fun cooldownSeconds(context: Context): Int? {
        val raw = prefs(context).getString(KEY, null) ?: return null
        return try {
            val seconds = JSONObject(raw).optInt("duplicate_protection_seconds", -1)
            if (seconds > 0) seconds else null
        } catch (e: Throwable) {
            null
        }
    }

    /** Mirrors GateSettings.classify_event: "early" | "late" | "clockout" | "other". */
    fun classifyEvent(context: Context, nowMillis: Long): String {
        val raw = prefs(context).getString(KEY, null) ?: return "other"
        return try {
            val data = JSONObject(raw)
            val cal = Calendar.getInstance().apply { timeInMillis = nowMillis }
            val minutes = cal.get(Calendar.HOUR_OF_DAY) * 60 + cal.get(Calendar.MINUTE)

            fun between(startKey: String, endKey: String): Boolean {
                val start = parseMinutes(data.optString(startKey, "")) ?: return false
                val end = parseMinutes(data.optString(endKey, "")) ?: return false
                return minutes in start..end
            }

            when {
                between("early_start", "early_end") -> "early"
                between("late_start", "late_end") -> "late"
                between("clockout_start", "clockout_end") -> "clockout"
                else -> "other"
            }
        } catch (e: Throwable) {
            "other"
        }
    }

    private fun parseMinutes(hhmmss: String): Int? {
        if (hhmmss.isEmpty()) return null
        val parts = hhmmss.split(":")
        if (parts.size < 2) return null
        val h = parts[0].toIntOrNull() ?: return null
        val m = parts[1].toIntOrNull() ?: return null
        return h * 60 + m
    }
}
