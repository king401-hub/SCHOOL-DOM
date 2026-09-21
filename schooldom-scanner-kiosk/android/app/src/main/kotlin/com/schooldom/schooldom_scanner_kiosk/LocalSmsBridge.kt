package com.schooldom.schooldom_scanner_kiosk

import android.Manifest
import android.app.Activity
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.telephony.SmsManager
import androidx.core.content.ContextCompat
import java.util.UUID

/**
 * Sends a gate-attendance SMS directly over the kiosk terminal's own SIM,
 * for when the terminal can't reach the backend at all (see
 * GuardianContactsCache/_handleScan's offline branch in
 * kiosk_home_screen.dart). SMS travels over the cellular signaling
 * channel, independent of whether the data/internet connection is up.
 *
 * [sendSms] only reports success once Android confirms every part of the
 * message was actually sent - not merely that the request was accepted. The
 * caller treats "true" as "the parent has been texted, so the server must NOT
 * text them again when the scan syncs", so a text that silently never left
 * (no airtime, no signal) has to come back as false or the parent would never
 * hear about it at all.
 */
class LocalSmsBridge(private val activity: MainActivity) {

    private val mainHandler = Handler(Looper.getMainLooper())

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

    /**
     * Calls [onResult] exactly once, on the main thread: true if the radio
     * reported the whole message sent, false on any failure - or if no report
     * arrived within [SEND_CONFIRM_TIMEOUT_MS] (unknown counts as failed: a
     * duplicate text when the server sends it too is far better than none).
     */
    fun sendSms(phone: String, message: String, onResult: (Boolean) -> Unit) {
        if (phone.isBlank() || !hasPermission()) {
            onResult(false)
            return
        }

        val context = activity.applicationContext
        val action = "$SENT_ACTION_PREFIX${UUID.randomUUID()}"
        var receiver: BroadcastReceiver? = null
        var timeout: Runnable? = null
        var finished = false

        fun finish(success: Boolean) {
            if (finished) return
            finished = true
            timeout?.let { mainHandler.removeCallbacks(it) }
            receiver?.let {
                try {
                    context.unregisterReceiver(it)
                } catch (e: Throwable) {
                    // Already unregistered.
                }
            }
            onResult(success)
        }

        try {
            val smsManager = SmsManager.getDefault()
            val parts = smsManager.divideMessage(message)
            var partsLeft = parts.size

            // One "sent" report arrives per part; the text only counts as sent
            // once all of them are OK.
            val sentReceiver = object : BroadcastReceiver() {
                override fun onReceive(c: Context?, intent: Intent?) {
                    if (resultCode != Activity.RESULT_OK) {
                        finish(false)
                        return
                    }
                    partsLeft -= 1
                    if (partsLeft <= 0) finish(true)
                }
            }
            receiver = sentReceiver
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                // Android 14+ requires saying whether a runtime receiver is exported.
                context.registerReceiver(sentReceiver, IntentFilter(action), Context.RECEIVER_NOT_EXPORTED)
            } else {
                context.registerReceiver(sentReceiver, IntentFilter(action))
            }

            val sentIntents = ArrayList<PendingIntent>(parts.size)
            for (i in parts.indices) {
                sentIntents.add(
                    PendingIntent.getBroadcast(
                        context, i, Intent(action).setPackage(context.packageName),
                        PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
                    ),
                )
            }

            val giveUp = Runnable { finish(false) }
            timeout = giveUp
            mainHandler.postDelayed(giveUp, SEND_CONFIRM_TIMEOUT_MS)

            smsManager.sendMultipartTextMessage(phone, null, parts, sentIntents, null)
        } catch (e: Throwable) {
            finish(false)
        }
    }

    companion object {
        const val REQUEST_CODE_SEND_SMS = 4177
        private const val SENT_ACTION_PREFIX = "com.schooldom.schooldom_scanner_kiosk.SMS_SENT_"
        private const val SEND_CONFIRM_TIMEOUT_MS = 10_000L
    }
}
