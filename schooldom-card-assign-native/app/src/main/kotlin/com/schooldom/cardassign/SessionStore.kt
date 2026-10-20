package com.schooldom.cardassign

import android.content.Context
import org.json.JSONObject

/** Holds the signed-in admin's JWT session (a JSON object with at least
 * "access", usually "refresh" too) - same shape/pattern as
 * schooldom-kiosk-native's SessionStore, backed by the same SecureStore. */
object SessionStore {
    private const val KEY_SESSION = "schooldom_card_assign_session"

    fun getSession(context: Context): JSONObject? {
        val raw = SecureStore.read(context, KEY_SESSION) ?: return null
        return try {
            JSONObject(raw)
        } catch (e: Throwable) {
            null
        }
    }

    fun saveSession(context: Context, session: JSONObject) {
        SecureStore.write(context, KEY_SESSION, session.toString())
    }

    fun clearSession(context: Context) {
        SecureStore.delete(context, KEY_SESSION)
    }
}
