package com.schooldom.cardassign

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.ProgressBar
import android.widget.TextView
import org.json.JSONObject
import java.util.concurrent.Executors

/** Plain email/password sign-in against the same /api/auth/login/ every
 * other SchoolDom client uses - no separate credential system. Handles the
 * admin-OTP step inline (a second code emailed to the same account) rather
 * than as a separate screen, since it's the exact same form just with one
 * more field shown. */
class LoginActivity : Activity() {
    private val bgExecutor = Executors.newSingleThreadExecutor()
    private val mainHandler = Handler(Looper.getMainLooper())

    private lateinit var emailInput: EditText
    private lateinit var passwordInput: EditText
    private lateinit var otpSection: View
    private lateinit var otpInput: EditText
    private lateinit var errorText: TextView
    private lateinit var progressBar: ProgressBar
    private lateinit var loginButton: Button
    private lateinit var otpVerifyButton: Button

    private var otpChallenge: String = ""

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_login)

        emailInput = findViewById(R.id.emailInput)
        passwordInput = findViewById(R.id.passwordInput)
        otpSection = findViewById(R.id.otpSection)
        otpInput = findViewById(R.id.otpInput)
        errorText = findViewById(R.id.errorText)
        progressBar = findViewById(R.id.progressBar)
        loginButton = findViewById(R.id.loginButton)
        otpVerifyButton = findViewById(R.id.otpVerifyButton)

        loginButton.setOnClickListener { onLoginTapped() }
        otpVerifyButton.setOnClickListener { onOtpVerifyTapped() }
    }

    private fun setBusy(busy: Boolean) {
        progressBar.visibility = if (busy) View.VISIBLE else View.GONE
        loginButton.isEnabled = !busy
        otpVerifyButton.isEnabled = !busy
    }

    private fun showError(message: String) {
        errorText.text = message
        errorText.visibility = View.VISIBLE
    }

    private fun onLoginTapped() {
        val email = emailInput.text.toString().trim()
        val password = passwordInput.text.toString()
        if (email.isEmpty() || password.isEmpty()) {
            showError("Enter your email and password.")
            return
        }
        errorText.visibility = View.GONE
        setBusy(true)
        bgExecutor.execute {
            try {
                val (status, body) = ApiClient.rawPost(
                    "/api/auth/login/",
                    JSONObject().apply { put("email", email); put("password", password) },
                )
                val data = if (body.isNotEmpty()) JSONObject(body) else JSONObject()
                mainHandler.post { handleAuthResponse(status, data, email) }
            } catch (e: Exception) {
                mainHandler.post {
                    setBusy(false)
                    showError("Could not reach the server. Check your connection.")
                }
            }
        }
    }

    private fun onOtpVerifyTapped() {
        val email = emailInput.text.toString().trim()
        val code = otpInput.text.toString().trim()
        if (code.length != 6) {
            showError("Enter the 6-digit code.")
            return
        }
        errorText.visibility = View.GONE
        setBusy(true)
        bgExecutor.execute {
            try {
                val (status, body) = ApiClient.rawPost(
                    "/api/auth/admin/verify-otp/",
                    JSONObject().apply { put("email", email); put("code", code); put("challenge", otpChallenge) },
                )
                val data = if (body.isNotEmpty()) JSONObject(body) else JSONObject()
                mainHandler.post { handleAuthResponse(status, data, email) }
            } catch (e: Exception) {
                mainHandler.post {
                    setBusy(false)
                    showError("Could not reach the server. Check your connection.")
                }
            }
        }
    }

    private fun handleAuthResponse(status: Int, data: JSONObject, email: String) {
        setBusy(false)
        if (status !in 200..299 || !data.optBoolean("success", false)) {
            showError(data.optString("message", "Sign in failed ($status)."))
            return
        }
        if (data.optBoolean("requires_otp", false)) {
            otpChallenge = data.optString("otp_challenge", "")
            otpSection.visibility = View.VISIBLE
            otpInput.requestFocus()
            return
        }
        val access = data.optString("access", "")
        if (access.isEmpty()) {
            showError("Sign in succeeded but no session was returned - try again.")
            return
        }
        val session = JSONObject().apply {
            put("access", access)
            if (data.has("refresh")) put("refresh", data.getString("refresh"))
        }
        SessionStore.saveSession(this, session)
        val role = data.optJSONObject("user")?.optString("role", "") ?: ""
        CardAssignStore.setUser(this, email, role)

        val next = if (CardAssignStore.needsSchoolPicker(this)) {
            Intent(this, SchoolPickerActivity::class.java)
        } else {
            Intent(this, StudentPickerActivity::class.java)
        }
        startActivity(next)
        finish()
    }
}
