package com.schooldom.schooldom_scanner_kiosk

import android.content.Context

/**
 * Direct port of lib/kiosk/kiosk_store.dart. Kept separate from SessionStore
 * (which only holds the generic access/refresh session JSON) - this holds
 * terminal-only bookkeeping: whether this device has been provisioned yet,
 * and its own identity for the heartbeat endpoint (a different credential -
 * see device_fleet.views._device_from_token on the backend).
 */
object KioskStore {
    private const val K_ENABLED = "kiosk_mode_enabled"
    private const val K_DEVICE_ID = "kiosk_device_id"
    private const val K_DEVICE_AUTH_TOKEN = "kiosk_device_auth_token"
    private const val K_SCHOOL_NAME = "kiosk_school_name"
    private const val K_SCHOOL_ID = "kiosk_school_id"
    private const val K_PAIRED_SCHOOL_ID = "kiosk_paired_school_id"
    private const val K_PAIRED_SCHOOL_NAME = "kiosk_paired_school_name"

    fun isEnabled(context: Context): Boolean = SecureStore.read(context, K_ENABLED) == "true"

    fun activate(context: Context, deviceId: String, deviceAuthToken: String, schoolName: String) {
        SecureStore.write(context, K_ENABLED, "true")
        SecureStore.write(context, K_DEVICE_ID, deviceId)
        SecureStore.write(context, K_DEVICE_AUTH_TOKEN, deviceAuthToken)
        SecureStore.write(context, K_SCHOOL_NAME, schoolName)
    }

    fun deviceId(context: Context): String? = SecureStore.read(context, K_DEVICE_ID)
    fun deviceAuthToken(context: Context): String? = SecureStore.read(context, K_DEVICE_AUTH_TOKEN)
    fun schoolName(context: Context): String? = SecureStore.read(context, K_SCHOOL_NAME)
    fun schoolId(context: Context): String? = SecureStore.read(context, K_SCHOOL_ID)
    fun pairedSchoolId(context: Context): String? = SecureStore.read(context, K_PAIRED_SCHOOL_ID)
    fun pairedSchoolName(context: Context): String? = SecureStore.read(context, K_PAIRED_SCHOOL_NAME)

    /** Called from the heartbeat response and after a successful switch, so a
     * restarted app shows the real current school immediately. */
    fun setActiveSchool(context: Context, id: String, name: String) {
        SecureStore.write(context, K_SCHOOL_ID, id)
        SecureStore.write(context, K_SCHOOL_NAME, name)
    }

    /** null for both clears the pairing. */
    fun setPairedSchool(context: Context, id: String?, name: String?) {
        if (id == null || name == null) {
            SecureStore.delete(context, K_PAIRED_SCHOOL_ID)
            SecureStore.delete(context, K_PAIRED_SCHOOL_NAME)
            return
        }
        SecureStore.write(context, K_PAIRED_SCHOOL_ID, id)
        SecureStore.write(context, K_PAIRED_SCHOOL_NAME, name)
    }

    /** Called either after a superadmin remote-revokes (authorized:false on a
     * heartbeat/scan response), or from a confirmation-gated "Re-enter
     * license key?" action - not a bare one-tap sign-out. */
    fun deactivate(context: Context) {
        for (k in listOf(K_ENABLED, K_DEVICE_ID, K_DEVICE_AUTH_TOKEN, K_SCHOOL_NAME, K_SCHOOL_ID, K_PAIRED_SCHOOL_ID, K_PAIRED_SCHOOL_NAME)) {
            SecureStore.delete(context, k)
        }
    }
}
