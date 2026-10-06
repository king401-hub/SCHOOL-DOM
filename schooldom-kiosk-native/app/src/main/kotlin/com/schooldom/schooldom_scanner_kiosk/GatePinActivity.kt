package com.schooldom.schooldom_scanner_kiosk

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.ProgressBar
import android.widget.TextView
import java.util.concurrent.Executors

/**
 * Direct port of GatePinScreen in gate_settings_screen.dart - a bare
 * numeric PIN gate shown before GateSettingsActivity, matching spec section
 * 6's "Settings should be protected by an admin PIN/authentication."
 */
class GatePinActivity : Activity() {
    private val worker = Executors.newSingleThreadExecutor()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_gate_pin)

        val pinInput = findViewById<EditText>(R.id.pinInput)
        val pinError = findViewById<TextView>(R.id.pinError)
        val continueButton = findViewById<Button>(R.id.continueButton)
        val busy = findViewById<ProgressBar>(R.id.pinBusy)

        fun submit() {
            pinError.visibility = View.GONE
            continueButton.isEnabled = false
            busy.visibility = View.VISIBLE
            val pin = pinInput.text.toString().trim()
            worker.execute {
                try {
                    val valid = GateEndpoints.verifyGatePin(this, pin)
                    runOnUiThread {
                        busy.visibility = View.GONE
                        continueButton.isEnabled = true
                        if (valid) {
                            startActivity(Intent(this, GateSettingsActivity::class.java))
                            finish()
                        } else {
                            pinError.text = "Incorrect PIN."
                            pinError.visibility = View.VISIBLE
                        }
                    }
                } catch (e: Exception) {
                    runOnUiThread {
                        busy.visibility = View.GONE
                        continueButton.isEnabled = true
                        pinError.text = e.message ?: "Could not verify PIN."
                        pinError.visibility = View.VISIBLE
                    }
                }
            }
        }

        continueButton.setOnClickListener { submit() }
    }
}
