package com.schooldom.schooldom_scanner_kiosk

import android.app.Activity
import android.content.Intent
import android.os.Bundle

/**
 * Direct port of main.dart's _KioskRoot: this app has exactly two states,
 * ever - unprovisioned (route to the license key entry screen) or
 * provisioned (route to the scanner terminal). No navigation menu, no
 * settings, no sign-out. SharedPreferences reads are synchronous and fast
 * enough natively that the artificial splash delay main.dart uses (to let
 * the branded animation play) isn't needed here - a plain launch_background
 * drawable (see res/drawable) covers the instant before this Activity draws.
 */
class MainActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        ApiClient.init(this)
        val next = if (KioskStore.isEnabled(this)) {
            Intent(this, KioskHomeActivity::class.java)
        } else {
            Intent(this, ProvisioningActivity::class.java)
        }
        startActivity(next)
        finish()
    }
}
