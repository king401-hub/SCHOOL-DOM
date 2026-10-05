package com.schooldom.schooldom_scanner_kiosk

import android.content.Context
import android.util.Log
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.UUID
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

enum class ScanOutcome { WELCOME, GOODBYE, INVALID, DUPLICATE, ERROR }

data class ScanResult(val outcome: ScanOutcome, val message: String?, val data: JSONObject?)

/**
 * Direct port of kiosk_home_screen.dart's _handleScan, including the offline
 * branch: a guardian-contact-cache lookup + direct SMS text to the parent
 * from the terminal's own SIM when the backend can't be reached at all, with
 * gate-settings-driven early/late/clockout wording (direction - clock-in vs
 * clock-out - still can't be known offline; see GateSettingsCache).
 */
object ScanHandler {
    // Spec section 7: a card held too long shouldn't be recorded repeatedly
    // in one tap.
    private const val DEFAULT_COOLDOWN_SECONDS = 8
    private val SCAN_READ_TIMEOUT_MS = 3_000L
    private val SMS_WAIT_TIMEOUT_MS = 12_000L

    private val worker = Executors.newSingleThreadExecutor()
    private val recentScans = mutableMapOf<String, Long>()

    @Volatile var cooldownSeconds: Int = DEFAULT_COOLDOWN_SECONDS

    private fun looksLikeAlreadyHandled(message: String): Boolean {
        val m = message.lowercase()
        return "already" in m || "wait" in m || "recently" in m
    }

    private fun formatTime(millis: Long): String {
        return SimpleDateFormat("h:mm a", Locale.US).format(Date(millis))
    }

    /** Runs on a background thread; calls [onResult] on that same thread -
     * the caller is responsible for hopping back to the main thread.
     * [smsBridge] may be null (e.g. SEND_SMS permission not yet granted);
     * the offline branch degrades to a generic "will sync" message when so. */
    fun handleScan(
        context: Context,
        uid: String,
        smsBridge: LocalSmsBridge?,
        onBusyChanged: (Boolean) -> Unit,
        onResult: (ScanResult) -> Unit,
    ) {
        val now = System.currentTimeMillis()
        val lastAt = recentScans[uid]
        if (lastAt != null && (now - lastAt) / 1000 < cooldownSeconds) {
            onResult(ScanResult(ScanOutcome.DUPLICATE, "Attendance already recorded at ${formatTime(lastAt)}.", null))
            return
        }
        recentScans[uid] = now
        recentScans.entries.removeAll { (now - it.value) > 10 * 60 * 1000 }

        onBusyChanged(true)
        val idempotencyKey = UUID.randomUUID().toString()
        worker.execute {
            try {
                val payload = JSONObject().apply {
                    put("card_uid", uid)
                    put("idempotency_key", idempotencyKey)
                    put("device_id", KioskStore.deviceId(context))
                }
                val result = ApiClient.apiRequest(
                    context, "POST", "/api/rfid/attendance/scan/",
                    payload = payload, queueWhenOffline = true, timeoutMs = SCAN_READ_TIMEOUT_MS,
                )

                if (result.optBoolean("offline", false)) {
                    onResult(handleOfflineScan(context, uid, idempotencyKey, smsBridge, result.optBoolean("timed_out", false)))
                    return@execute
                }

                val action = result.optString("action", "")
                val combined = JSONObject().apply {
                    result.optJSONObject("person")?.let { person ->
                        person.keys().forEach { k -> put(k, person.get(k)) }
                    }
                    put("fees", result.opt("fees"))
                    put("student_dva", result.opt("student_dva"))
                    put("attendance_event", result.opt("attendance_event"))
                }
                val outcome = if (action == "clock_out") ScanOutcome.GOODBYE else ScanOutcome.WELCOME
                val message = if (result.has("message") && !result.isNull("message")) result.getString("message") else null
                onResult(ScanResult(outcome, message, combined))
            } catch (e: ApiException) {
                val outcome = when {
                    e.statusCode == 404 -> ScanOutcome.INVALID
                    e.statusCode == 400 && looksLikeAlreadyHandled(e.message ?: "") -> ScanOutcome.DUPLICATE
                    else -> ScanOutcome.ERROR
                }
                onResult(ScanResult(outcome, e.message, null))
            } catch (e: SessionExpiredException) {
                onResult(ScanResult(ScanOutcome.ERROR, "This terminal has been logged out remotely.", null))
            } catch (e: Exception) {
                Log.e("ScanHandler", "Unexpected error handling scan", e)
                onResult(ScanResult(ScanOutcome.ERROR, "Unable to record attendance. Please try again.", null))
            } finally {
                onBusyChanged(false)
            }
        }
    }

    /**
     * Either no network at all, or the backend didn't answer within
     * SCAN_READ_TIMEOUT_MS - either way this goes on what is cached. The
     * queue mechanism in ApiClient blindly stores ANY scan, so check the
     * last-synced assignment snapshot ourselves before claiming success for
     * a card that was never actually registered. An unknown card can never
     * succeed once replayed either, so drop it from the queue instead of
     * leaving it stuck retrying forever.
     */
    private fun handleOfflineScan(
        context: Context,
        uid: String,
        idempotencyKey: String,
        smsBridge: LocalSmsBridge?,
        timedOut: Boolean,
    ): ScanResult {
        val contact = GuardianContactsCache.lookup(context, uid)
        if (contact == null && timedOut) {
            // The backend is only slow, not unreachable, so it may well know
            // this card - our cache just doesn't. Keep the scan queued for
            // the replay to settle instead of telling a real student their
            // card is unregistered.
            return ScanResult(ScanOutcome.WELCOME, "Saved - will sync when back online.", null)
        }
        if (contact == null) {
            OfflineQueue.removeByIdempotencyKey(context, idempotencyKey)
            return ScanResult(ScanOutcome.INVALID, "Card not recognized (offline).", null)
        }

        val event = GateSettingsCache.classifyEvent(context, System.currentTimeMillis())
        val outcome = if (event == "clockout") ScanOutcome.GOODBYE else ScanOutcome.WELCOME
        var message = "Saved - will sync when back online."

        val phone = contact["phone"] ?: ""
        if (phone.isNotEmpty() && smsBridge != null) {
            val name = contact["name"]?.ifEmpty { "Student" } ?: "Student"
            val timeText = formatTime(System.currentTimeMillis())
            val text = when (event) {
                "clockout" -> "$name left school at $timeText. -SchoolDom"
                "early" -> "$name arrived (early) at $timeText. -SchoolDom"
                "late" -> "$name arrived (late) at $timeText. -SchoolDom"
                else -> "$name was scanned at the school gate at $timeText. -SchoolDom"
            }
            val latch = CountDownLatch(1)
            var sent = false
            smsBridge.sendSms(phone, text) { ok -> sent = ok; latch.countDown() }
            latch.await(SMS_WAIT_TIMEOUT_MS, TimeUnit.MILLISECONDS)
            message = if (sent) {
                OfflineQueue.markSmsSentLocally(context, idempotencyKey)
                "Saved - parent texted directly (offline)."
            } else {
                // The SIM couldn't send it (no airtime, no signal...). The
                // scan is deliberately NOT flagged sms_sent_locally, so the
                // server texts the parent itself once the scan syncs.
                "Saved - SMS failed (check SIM airtime). Parent will be texted once back online."
            }
        }
        return ScanResult(outcome, message, null)
    }
}
