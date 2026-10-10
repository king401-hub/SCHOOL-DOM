package com.schooldom.schooldom_scanner_kiosk

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.Toast

/**
 * Settings screen's "Check SIM Balance" - dials whatever USSD code the admin
 * types (e.g. *556# for MTN) over the terminal's own SIM, the same way
 * manually dialing it in the system Phone app would. Deliberately does not
 * try to capture/parse the carrier's response itself (that needs
 * TelephonyManager.sendUssdRequest, API 26+ only - this fleet's confirmed
 * floor is API 24, see build.gradle.kts) - the response shows in Android's
 * own native USSD reply dialog instead, which every admin already
 * recognizes, and keeps this screen to a single lightweight Activity with no
 * version branching.
 */
class UssdActivity : Activity() {
    private var pendingUssdCode: String? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_ussd)

        val input = findViewById<EditText>(R.id.ussdInput)
        val dialButton = findViewById<Button>(R.id.ussdDialButton)
        findViewById<View>(R.id.backButton).setOnClickListener { finish() }

        dialButton.setOnClickListener {
            val code = input.text.toString().trim()
            if (code.isEmpty()) return@setOnClickListener
            dialUssd(code)
        }
    }

    private fun dialUssd(code: String) {
        if (checkSelfPermission(Manifest.permission.CALL_PHONE) != PackageManager.PERMISSION_GRANTED) {
            pendingUssdCode = code
            requestPermissions(arrayOf(Manifest.permission.CALL_PHONE), REQUEST_CALL_PHONE)
            return
        }
        launchUssdCall(code)
    }

    private fun launchUssdCall(code: String) {
        val encoded = code.replace("#", Uri.encode("#"))
        try {
            startActivity(Intent(Intent.ACTION_CALL, Uri.parse("tel:$encoded")))
        } catch (e: Exception) {
            Toast.makeText(this, "Could not dial: ${e.message}", Toast.LENGTH_SHORT).show()
        }
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == REQUEST_CALL_PHONE) {
            val code = pendingUssdCode
            pendingUssdCode = null
            if (grantResults.firstOrNull() == PackageManager.PERMISSION_GRANTED && code != null) {
                launchUssdCall(code)
            } else {
                Toast.makeText(this, "Call permission is needed to dial a USSD code.", Toast.LENGTH_SHORT).show()
            }
        }
    }

    companion object {
        private const val REQUEST_CALL_PHONE = 4180
    }
}
