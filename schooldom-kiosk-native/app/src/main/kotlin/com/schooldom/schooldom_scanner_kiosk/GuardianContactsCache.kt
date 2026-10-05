package com.schooldom.schooldom_scanner_kiosk

import android.content.Context
import org.json.JSONObject

/**
 * Direct port of lib/storage/guardian_contacts_cache.dart: a local snapshot
 * of {card_uid -> {name, phone, role}}, pulled from
 * /api/rfid/card-assignments/ (the same active-assignment list the Win7
 * desktop app already relies on for offline card matching). Lets the kiosk
 * text a parent directly via the terminal's own SIM when a scan can't reach
 * the backend at all - see ScanHandler's offline branch.
 */
object GuardianContactsCache {
    private const val PREFS_NAME = "schooldom_guardian_contacts_store"
    private const val KEY = "guardian_contacts_cache"

    private fun prefs(context: Context) =
        context.applicationContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    /** True when the list was pulled and saved, false when it could not be
     * (the previous copy is kept) - so a caller can retry sooner after a
     * failure than after a success. Blocking - call off the main thread. */
    fun refresh(context: Context): Boolean {
        return try {
            val result = ApiClient.getJson(context, "/api/rfid/card-assignments/")
            val rows = result.optJSONArray("data")
            val map = JSONObject()
            if (rows != null) {
                for (i in 0 until rows.length()) {
                    val row = rows.optJSONObject(i) ?: continue
                    val uid = row.optString("card_uid", "")
                    if (uid.isEmpty()) continue
                    val entry = JSONObject().apply {
                        put("name", row.optString("person_name", ""))
                        put("phone", row.optString("guardian_phone", ""))
                        put("role", row.optString("role", ""))
                    }
                    map.put(uid, entry)
                }
            }
            prefs(context).edit().putString(KEY, map.toString()).apply()
            true
        } catch (e: Throwable) {
            false
        }
    }

    fun lookup(context: Context, cardUid: String): Map<String, String>? {
        val raw = prefs(context).getString(KEY, null) ?: return null
        return try {
            val map = JSONObject(raw)
            val entry = map.optJSONObject(cardUid) ?: return null
            mapOf(
                "name" to entry.optString("name", ""),
                "phone" to entry.optString("phone", ""),
                "role" to entry.optString("role", ""),
            )
        } catch (e: Throwable) {
            null
        }
    }
}
