package com.schooldom.schooldom_scanner_kiosk

import android.content.Context
import org.json.JSONObject

/**
 * Direct port of lib/api/gate_endpoints.dart. NOT YET PORTED: setGatePin
 * (changing the PIN itself) - the Settings screen can view/edit the
 * operating mode, attendance windows, and duplicate-protection interval,
 * same as the Flutter app, but PIN rotation is a separate follow-up.
 */
object GateEndpoints {
    fun loadGateSettings(context: Context): JSONObject =
        ApiClient.getJson(context, "/api/rfid/gate-settings/")

    fun updateGateSettings(context: Context, fields: JSONObject): JSONObject =
        ApiClient.postJson(context, "/api/rfid/gate-settings/update/", fields)

    /** Empty pin ("") is valid here - gate_pin_verify treats "no PIN
     * configured yet" as always-valid, so a fresh terminal's Settings screen
     * never locks an admin out before they've set one up. */
    fun verifyGatePin(context: Context, pin: String): Boolean {
        val data = ApiClient.postJson(context, "/api/rfid/gate-settings/verify-pin/", JSONObject().put("pin", pin))
        return data.optBoolean("valid", false)
    }

    /** The spec's on-demand "Send Fee Reminder" button - distinct from the
     * automatic per-scan attendance SMS, which the backend sends on its own
     * without the app asking. */
    fun sendFeeReminder(context: Context, studentId: String): JSONObject =
        ApiClient.postJson(context, "/api/rfid/fee-reminder/send/", JSONObject().put("student_id", studentId))
}
