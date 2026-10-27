package com.schooldom.schooldom_scanner_kiosk

import android.content.Context
import android.util.Log
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.UUID
import java.util.concurrent.Executors

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
    // The budget for the whole scan-to-result round trip, online or
    // offline - a card tap at the gate must get an answer quickly, so
    // nothing in this file (network call, offline SMS fallback) is allowed
    // to block longer than this.
    private val SCAN_READ_TIMEOUT_MS = 3_000L

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

    private fun formatDate(millis: Long): String {
        return SimpleDateFormat("MMM d", Locale.US).format(Date(millis))
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
                    // The real moment of the tap, not whenever this request
                    // actually gets sent - matters once a scan queues offline
                    // and replays later, possibly a day or more afterward
                    // (see OfflineQueue/ApiClient.replayOfflineQueue). The
                    // backend ignores this when missing, malformed, or wildly
                    // out of bounds - see rfid_attendance.views._parse_scanned_at.
                    put("scanned_at", isoAt(now))
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
            // card is unregistered. The UID is shown regardless, same
            // reasoning as the branch below - an admin reading it off this
            // screen to assign the card shouldn't have to care which exact
            // path produced the message.
            return ScanResult(ScanOutcome.WELCOME, "Card $uid saved - will sync when back online.", null)
        }
        if (contact == null) {
            OfflineQueue.removeByIdempotencyKey(context, idempotencyKey)
            // The raw UID is what an admin reads off this screen to type
            // into the web "Assign Card" form - the online path already
            // includes it (the server's own "Card <uid> is not linked to
            // anyone." message), so the offline path must too, or the
            // terminal is useless for card assignment whenever it isn't
            // fully online.
            return ScanResult(ScanOutcome.INVALID, "Card $uid is not recognized (offline).", null)
        }

        val event = GateSettingsCache.classifyEvent(context, System.currentTimeMillis())
        val outcome = if (event == "clockout") ScanOutcome.GOODBYE else ScanOutcome.WELCOME
        var message = "Saved - will sync when back online."

        val phone = contact["phone"] ?: ""
        if (phone.isNotEmpty() && smsBridge != null) {
            val name = contact["name"]?.ifEmpty { "Student" } ?: "Student"
            val nowMillis = System.currentTimeMillis()
            val timeText = formatTime(nowMillis)
            val dateText = formatDate(nowMillis)
            // Signed with the school's own name - this message is the
            // school talking to its own parents, not a platform
            // notification. Matches the backend's own _gate_sms_text.
            val schoolName = KioskStore.schoolName(context) ?: "SchoolDom"
            val text = when (event) {
                "clockout" -> "$name left school at $timeText on $dateText. -$schoolName"
                "early" -> "$name arrived (early) at $timeText on $dateText. -$schoolName"
                "late" -> "$name arrived (late) at $timeText on $dateText. -$schoolName"
                else -> "$name was scanned at the school gate at $timeText on $dateText. -$schoolName"
            }
            // Fire-and-forget: a card tap must still show a result within
            // SCAN_READ_TIMEOUT_MS regardless of path, offline included -
            // waiting here for the SIM to confirm the text (previously up
            // to SMS_WAIT_TIMEOUT_MS=12s on top of that) made a card read
            // take far longer than that whenever offline. The queued scan
            // already exists (OfflineQueue.enqueue, called before this
            // branch runs), so flagging it sms-sent-locally a moment later
            // from this background callback is still in time for whenever
            // it actually replays.
            smsBridge.sendSms(phone, text) { ok ->
                if (ok) OfflineQueue.markSmsSentLocally(context, idempotencyKey)
            }
            message = "Saved - texting parent now (offline)."
        }
        return ScanResult(outcome, message, null)
    }
}
