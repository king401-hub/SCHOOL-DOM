package com.schooldom.cardassign

import android.content.Context

/** Plain (non-secret) local state for the current admin session - who's
 * signed in, which role, and which school is currently selected. The JWT
 * tokens themselves live in SessionStore/SecureStore, encrypted; none of
 * this needs that, it's just UI-flow state. */
object CardAssignStore {
    private const val PREFS = "schooldom_card_assign_prefs"

    private fun prefs(context: Context) = context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    fun setUser(context: Context, email: String, role: String) {
        prefs(context).edit().putString("user_email", email).putString("user_role", role).apply()
    }

    fun userEmail(context: Context): String = prefs(context).getString("user_email", "") ?: ""
    fun userRole(context: Context): String = prefs(context).getString("user_role", "") ?: ""

    /** Only super_admin needs to pick which school to work in - everyone
     * else (school_admin/principal) always acts on their own school. */
    fun needsSchoolPicker(context: Context): Boolean = userRole(context) == "super_admin"

    fun setSchool(context: Context, schoolCode: String, schoolName: String) {
        prefs(context).edit().putString("school_code", schoolCode).putString("school_name", schoolName).apply()
    }

    fun schoolCode(context: Context): String = prefs(context).getString("school_code", "") ?: ""
    fun schoolName(context: Context): String = prefs(context).getString("school_name", "") ?: ""

    fun clearSchool(context: Context) {
        prefs(context).edit().remove("school_code").remove("school_name").apply()
    }

    fun clearAll(context: Context) {
        prefs(context).edit().clear().apply()
    }
}
