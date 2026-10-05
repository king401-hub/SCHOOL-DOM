package com.schooldom.schooldom_scanner_kiosk

import android.content.Context
import org.json.JSONObject

/** Direct port of lib/storage/session_store.dart - same key, same shape
 * (a JSON object with at least "access", usually "refresh" too), just backed
 * by SecureStore instead of FlutterSecureStorage. */
object SessionStore {
    private const val KEY_SESSION = "schooldom_scanner_session"

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
