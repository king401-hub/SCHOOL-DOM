package com.schooldom.schooldom_scanner_kiosk

import android.app.Activity
import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.util.Log
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.ProgressBar
import android.widget.TextView
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.Executors

/**
 * Direct port of lib/kiosk/kiosk_provisioning_screen.dart - same endpoint,
 * same payload shape, same response contract (201 + body.data with
 * access_token/refresh_token/device_id/auth_token). Spec section 11: the
 * very first screen a freshly-installed terminal shows; never appears again
 * once provisioned (see MainActivity's routing).
 */
class ProvisioningActivity : Activity() {
    private val worker = Executors.newSingleThreadExecutor()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_provisioning)

        val keyInput = findViewById<EditText>(R.id.licenseKeyInput)
        val errorText = findViewById<TextView>(R.id.errorText)
        val activateButton = findViewById<Button>(R.id.activateButton)
        val busyIndicator = findViewById<ProgressBar>(R.id.busyIndicator)

        fun setBusy(busy: Boolean) {
            activateButton.isEnabled = !busy
            busyIndicator.visibility = if (busy) View.VISIBLE else View.GONE
        }

        fun showError(message: String) {
            errorText.text = message
            errorText.visibility = View.VISIBLE
        }

        activateButton.setOnClickListener {
            val key = keyInput.text.toString().trim()
            if (key.isEmpty()) {
                showError("Enter the device license key.")
                return@setOnClickListener
            }
            errorText.visibility = View.GONE
            setBusy(true)

            worker.execute {
                try {
                    // Real device_model/os_version/app_version - spec section 28:
                    // never hardcode/guess, blank if unavailable (the backend
                    // already treats a blank value as "unknown").
                    val deviceModel = "${Build.MANUFACTURER} ${Build.MODEL}".trim()
                    val osVersion = "Android ${Build.VERSION.RELEASE}"
                    val appVersion = try {
                        packageManager.getPackageInfo(packageName, 0).versionName ?: ""
                    } catch (e: Exception) {
                        ""
                    }

                    val payload = JSONObject().apply {
                        put("provisioning_key", key)
                        put("device_name", "SchoolDom Scanner")
                        put("device_model", deviceModel)
                        put("os_version", osVersion)
                        put("app_version", appVersion)
                    }

                    val (status, body) = ApiClient.rawPost("/api/device-fleet/device/provision/", payload)
                    val data = if (body.isNotEmpty()) JSONObject(body) else JSONObject()

                    if (status != 201 || data.isNull("data") || !data.has("data")) {
                        val message = if (data.has("message") && !data.isNull("message")) {
                            data.getString("message")
                        } else {
                            "Could not activate this device. Check the key and try again."
                        }
                        runOnUiThread {
                            setBusy(false)
                            showError(message)
                        }
                        return@execute
                    }

                    val result = data.getJSONObject("data")
                    val session = JSONObject().apply {
                        put("access", result.getString("access_token"))
                        put("refresh", result.getString("refresh_token"))
                        put("signedInAt", isoNow())
                    }
                    SessionStore.saveSession(this@ProvisioningActivity, session)
                    KioskStore.activate(
                        this@ProvisioningActivity,
                        deviceId = result.getString("device_id"),
                        deviceAuthToken = result.getString("auth_token"),
                        schoolName = "Waiting for school assignment",
                    )

                    runOnUiThread {
                        startActivity(Intent(this@ProvisioningActivity, KioskHomeActivity::class.java))
                        finish()
                    }
                } catch (e: IOException) {
                    Log.e("ProvisioningActivity", "Network error during activation", e)
                    runOnUiThread {
                        setBusy(false)
                        showError("Network error - could not reach the SchoolDom server.")
                    }
                } catch (e: Exception) {
                    Log.e("ProvisioningActivity", "Unexpected error during activation", e)
                    runOnUiThread {
                        setBusy(false)
                        showError("Network error - could not reach the SchoolDom server.")
                    }
                }
            }
        }
    }
}
