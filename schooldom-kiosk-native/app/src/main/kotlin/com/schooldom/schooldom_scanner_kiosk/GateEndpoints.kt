package com.schooldom.schooldom_scanner_kiosk

import android.content.Context
import org.json.JSONObject

/**
 * Direct port of lib/api/gate_endpoints.dart's loadGateSettings/
 * sendFeeReminder. NOT YET PORTED: verifyGatePin/setGatePin/
 * updateGateSettings - the PIN-protected Settings screen itself (mode,
 * attendance windows, duplicate-protection interval, PIN change) is a
 * separate follow-up; today's scope only needs read access to the current
 * settings (for the cooldown + GateSettingsCache) and the on-demand fee
 * reminder send.
 */
object GateEndpoints {
    fun loadGateSettings(context: Context): JSONObject =
        ApiClient.getJson(context, "/api/rfid/gate-settings/")

    /** The spec's on-demand "Send Fee Reminder" button - distinct from the
     * automatic per-scan attendance SMS, which the backend sends on its own
     * without the app asking. */
    fun sendFeeReminder(context: Context, studentId: String): JSONObject =
        ApiClient.postJson(context, "/api/rfid/fee-reminder/send/", JSONObject().put("student_id", studentId))
}
