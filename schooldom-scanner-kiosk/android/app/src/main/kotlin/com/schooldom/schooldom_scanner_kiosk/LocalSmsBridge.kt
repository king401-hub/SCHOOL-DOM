package com.schooldom.schooldom_scanner_kiosk

import android.Manifest
import android.content.pm.PackageManager
import android.telephony.SmsManager
import androidx.core.content.ContextCompat

/**
 * Sends a gate-attendance SMS directly over the kiosk terminal's own SIM,
 * for when the terminal can't reach the backend at all (see
 * GuardianContactsCache/_handleScan's offline branch in
 * kiosk_home_screen.dart). SMS travels over the cellular signaling
 * channel, independent of whether the data/internet connection is up.
 */
class LocalSmsBridge(private val activity: MainActivity) {

    fun hasPermission(): Boolean =
        ContextCompat.checkSelfPermission(activity, Manifest.permission.SEND_SMS) ==
            PackageManager.PERMISSION_GRANTED

    fun requestPermission() {
        if (!hasPermission()) {
            androidx.core.app.ActivityCompat.requestPermissions(
                activity, arrayOf(Manifest.permission.SEND_SMS), REQUEST_CODE_SEND_SMS,
            )
        }
    }

    fun sendSms(phone: String, message: String): Boolean {
        if (phone.isBlank() || !hasPermission()) return false
        return try {
            val smsManager = SmsManager.getDefault()
            val parts = smsManager.divideMessage(message)
            smsManager.sendMultipartTextMessage(phone, null, parts, null, null)
            true
        } catch (e: Throwable) {
            false
        }
    }

    companion object {
        const val REQUEST_CODE_SEND_SMS = 4177
    }
}
