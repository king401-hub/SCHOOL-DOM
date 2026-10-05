package com.schooldom.schooldom_scanner_kiosk

import android.content.Context
import android.util.Log
import org.json.JSONObject
import java.util.UUID
import java.util.concurrent.Executors

enum class ScanOutcome { WELCOME, GOODBYE, INVALID, DUPLICATE, ERROR }

data class ScanResult(val outcome: ScanOutcome, val message: String?, val data: JSONObject?)

/**
 * Direct port of kiosk_home_screen.dart's _handleScan - the core submit path
 * only. NOT YET PORTED (tracked follow-up, not silently dropped): the
 * offline branch's guardian-contact-cache lookup + direct SMS text to the
 * parent when the backend is unreachable, and gate-settings-driven
 * early/late/clockout wording. For now, an offline/timed-out scan just
 * queues and shows a generic "will sync when back online" - correct and
 * safe, just not yet as informative as the Flutter app's offline branch.
 */
object ScanHandler {
    // Spec section 7: a card held too long shouldn't be recorded repeatedly
    // in one tap.
    private const val DEFAULT_COOLDOWN_SECONDS = 8
    private val SCAN_READ_TIMEOUT_MS = 3_000L

    private val worker = Executors.newSingleThreadExecutor()
    private val recentScans = mutableMapOf<String, Long>()

    @Volatile var cooldownSeconds: Int = DEFAULT_COOLDOWN_SECONDS

    private fun looksLikeAlreadyHandled(message: String): Boolean {
        val m = message.lowercase()
        return "already" in m || "wait" in m || "recently" in m
    }

    /** Runs on a background thread; calls [onResult] on that same thread -
     * the caller is responsible for hopping back to the main thread. */
    fun handleScan(context: Context, uid: String, onBusyChanged: (Boolean) -> Unit, onResult: (ScanResult) -> Unit) {
        val now = System.currentTimeMillis()
        val lastAt = recentScans[uid]
        if (lastAt != null && (now - lastAt) / 1000 < cooldownSeconds) {
            onResult(ScanResult(ScanOutcome.DUPLICATE, "Attendance already recorded.", null))
            return
        }
        recentScans[uid] = now
        recentScans.entries.removeAll { (now - it.value) > 10 * 60 * 1000 }

        onBusyChanged(true)
        worker.execute {
            try {
                val payload = JSONObject().apply {
                    put("card_uid", uid)
                    put("idempotency_key", UUID.randomUUID().toString())
                    put("device_id", KioskStore.deviceId(context))
                }
                val result = ApiClient.apiRequest(
                    context, "POST", "/api/rfid/attendance/scan/",
                    payload = payload, queueWhenOffline = true, timeoutMs = SCAN_READ_TIMEOUT_MS,
                )

                if (result.optBoolean("offline", false)) {
                    onResult(ScanResult(ScanOutcome.WELCOME, "Saved - will sync when back online.", null))
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
}
