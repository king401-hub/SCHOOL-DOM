package com.schooldom.cardassign

import android.app.Activity
import android.content.Intent
import android.os.Bundle

/** Entry point: routes straight to whichever step comes next for the
 * current state - signed out, needs a school picked, or ready to pick a
 * student and tap a card. No menu, no home screen of its own. */
class MainActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        ApiClient.init(this)

        val session = SessionStore.getSession(this)
        val next = when {
            session == null || session.optString("access", "").isEmpty() ->
                Intent(this, LoginActivity::class.java)
            CardAssignStore.needsSchoolPicker(this) && CardAssignStore.schoolCode(this).isEmpty() ->
                Intent(this, SchoolPickerActivity::class.java)
            else ->
                Intent(this, StudentPickerActivity::class.java)
        }
        startActivity(next)
        finish()
    }
}
