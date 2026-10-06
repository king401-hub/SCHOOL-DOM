package com.schooldom.schooldom_scanner_kiosk

import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.nfc.NfcAdapter
import android.nfc.Tag
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.tts.TextToSpeech
import android.view.KeyEvent
import android.view.View
import android.view.WindowManager
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import org.json.JSONObject
import java.util.Locale
import java.util.concurrent.Executors

/**
 * Direct (partial - see rewrite scope) port of kiosk_home_screen.dart: NFC
 * tap reading, the external USB HID keyboard-wedge reader path (same
 * inter-keystroke-timing technique as HidRfidReader.cs), scan submission via
 * ScanHandler (including its offline guardian-SMS fallback), heartbeat
 * reporting (battery/location/authorization/school-sync), gate-settings-
 * driven duplicate-protection cooldown, the Fee Tracker result card with
 * Print/Send SMS actions, and TTS feedback. NOT YET PORTED: the self-update
 * prompt, the PIN-protected Settings screen (mode/windows/PIN edit - this
 * activity only ever reads gate settings), and Device Owner/kiosk-lock mode.
 */
class KioskHomeActivity : Activity(), NfcAdapter.ReaderCallback {
    private lateinit var printerBridge: TopwisePrinterBridge
    private lateinit var smsBridge: LocalSmsBridge
    private var tts: TextToSpeech? = null
    private var nfcAdapter: NfcAdapter? = null
    private val mainHandler = Handler(Looper.getMainLooper())
    private val bgExecutor = Executors.newSingleThreadExecutor()

    private lateinit var readyBlock: View
    private lateinit var readyText: TextView
    private lateinit var schoolNameText: TextView
    private lateinit var statusDot: View
    private lateinit var statusText: TextView
    private lateinit var settingsButton: TextView
    private lateinit var reprovisionButton: TextView
    private lateinit var scanIcon: TextView
    private lateinit var resultBlock: LinearLayout
    private lateinit var resultIconBg: View
    private lateinit var resultIcon: TextView
    private lateinit var resultTitle: TextView
    private lateinit var resultName: TextView
    private lateinit var resultSubtitle: TextView
    private lateinit var resultText: TextView
    private lateinit var feeCard: LinearLayout
    private lateinit var feePaidText: TextView
    private lateinit var feeOutstandingText: TextView
    private lateinit var feeDvaText: TextView
    private lateinit var printButton: Button
    private lateinit var sendSmsButton: Button

    private var busy = false
    private var resetResultRunnable: Runnable? = null

    // ---- Heartbeat / connectivity state (mirrors kiosk_home_screen.dart) ----
    private val heartbeatIntervalMs = 5 * 60 * 1000L
    private val contactsRefreshIntervalMs = 30 * 60 * 1000L
    private var heartbeatInFlight = false
    private var online = true
    private var pendingCount = 0
    private var sessionExpired = false
    private var contactsRefreshedAt: Long? = null
    private var contactsRefreshing = false
    private val heartbeatRunnable = object : Runnable {
        override fun run() {
            sendHeartbeat()
            mainHandler.postDelayed(this, heartbeatIntervalMs)
        }
    }

    // Set by showResult when a fee card is shown, read by the Print/Send SMS
    // button handlers - both act on "whichever result is currently on screen".
    private data class FeeContext(
        val studentId: String,
        val name: String,
        val className: String,
        val paid: String,
        val outstanding: String,
        val dva: JSONObject?,
    )
    private var currentFeeContext: FeeContext? = null

    // ---- HID keyboard-wedge capture (mirrors kiosk_home_screen.dart's
    // _handleHidKeyEvent/_commitHidBuffer exactly: timing-based, not a
    // dedicated USB HID plugin - an external reader just "types" into
    // whichever window has input focus, which on a single-Activity kiosk is
    // always this one, so dispatchKeyEvent needs no explicit focus juggling
    // the way the Flutter FocusNode version did). ----
    private val hidBuffer = StringBuilder()
    private var hidBufferLooksLikeScan = true
    private var lastHidKeyAtMs: Long? = null
    private val hidFastKeystrokeThresholdMs = 50
    private val hidIdleResetMs = 400

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        setContentView(R.layout.activity_home)

        readyBlock = findViewById(R.id.readyBlock)
        readyText = findViewById(R.id.readyText)
        schoolNameText = findViewById(R.id.schoolNameText)
        statusDot = findViewById(R.id.statusDot)
        statusText = findViewById(R.id.statusText)
        settingsButton = findViewById(R.id.settingsButton)
        reprovisionButton = findViewById(R.id.reprovisionButton)
        scanIcon = findViewById(R.id.scanIcon)
        resultBlock = findViewById(R.id.resultBlock)
        resultIconBg = findViewById(R.id.resultIconBg)
        resultIcon = findViewById(R.id.resultIcon)
        resultTitle = findViewById(R.id.resultTitle)
        resultName = findViewById(R.id.resultName)
        resultSubtitle = findViewById(R.id.resultSubtitle)
        resultText = findViewById(R.id.resultText)
        feeCard = findViewById(R.id.feeCard)
        feePaidText = findViewById(R.id.feePaidText)
        feeOutstandingText = findViewById(R.id.feeOutstandingText)
        feeDvaText = findViewById(R.id.feeDvaText)
        printButton = findViewById(R.id.printButton)
        sendSmsButton = findViewById(R.id.sendSmsButton)

        schoolNameText.text = KioskStore.schoolName(this) ?: "Waiting for school assignment"
        updateStatusText()

        printerBridge = TopwisePrinterBridge(applicationContext)
        smsBridge = LocalSmsBridge(this)
        if (!smsBridge.hasPermission()) {
            smsBridge.requestPermission()
        }

        tts = TextToSpeech(this) { status ->
            if (status == TextToSpeech.SUCCESS) {
                tts?.language = Locale.US
                tts?.setSpeechRate(0.9f)
            }
            // A device with no TTS engine installed (common on locked-down
            // POS firmware) just means no voice feedback - never a crash.
        }

        nfcAdapter = NfcAdapter.getDefaultAdapter(this)

        reprovisionButton.setOnClickListener { confirmReProvision() }
        settingsButton.setOnClickListener { startActivity(Intent(this, GatePinActivity::class.java)) }
        printButton.setOnClickListener { onPrintTapped() }
        sendSmsButton.setOnClickListener { onSendSmsTapped() }

        loadGateSettings()
        mainHandler.post(heartbeatRunnable)
    }

    override fun onResume() {
        super.onResume()
        nfcAdapter?.enableReaderMode(
            this, this,
            NfcAdapter.FLAG_READER_NFC_A or NfcAdapter.FLAG_READER_NFC_B or
                NfcAdapter.FLAG_READER_NFC_F or NfcAdapter.FLAG_READER_NFC_V or
                NfcAdapter.FLAG_READER_SKIP_NDEF_CHECK,
            null,
        )
    }

    override fun onPause() {
        super.onPause()
        nfcAdapter?.disableReaderMode(this)
    }

    override fun onDestroy() {
        super.onDestroy()
        resetResultRunnable?.let { mainHandler.removeCallbacks(it) }
        mainHandler.removeCallbacks(heartbeatRunnable)
        tts?.stop()
        tts?.shutdown()
    }

    /** NfcAdapter.ReaderCallback - fires on a background thread. */
    override fun onTagDiscovered(tag: Tag) {
        val uid = tag.id?.joinToString("") { "%02X".format(it) }
        if (!uid.isNullOrEmpty()) {
            mainHandler.post { submitScan(uid) }
        }
    }

    // physicalKey-equivalent: Android's keyCode for a standard digit/letter
    // row is layout-independent the same way Flutter's physicalKey is, which
    // is what matters for a generic/unbranded USB HID reader that may be
    // assigned a non-US layout.
    private fun hidCharFor(keyCode: Int): Char? = when (keyCode) {
        in KeyEvent.KEYCODE_0..KeyEvent.KEYCODE_9 -> '0' + (keyCode - KeyEvent.KEYCODE_0)
        in KeyEvent.KEYCODE_A..KeyEvent.KEYCODE_Z -> 'A' + (keyCode - KeyEvent.KEYCODE_A)
        else -> null
    }

    override fun dispatchKeyEvent(event: KeyEvent): Boolean {
        if (event.action != KeyEvent.ACTION_DOWN) return super.dispatchKeyEvent(event)

        val now = System.currentTimeMillis()
        val gapMs = lastHidKeyAtMs?.let { now - it }
        lastHidKeyAtMs = now

        if (gapMs == null || gapMs > hidIdleResetMs) {
            hidBuffer.clear()
            hidBufferLooksLikeScan = true
        } else if (hidBuffer.isNotEmpty() && gapMs > hidFastKeystrokeThresholdMs) {
            hidBufferLooksLikeScan = false
        }

        if (event.keyCode == KeyEvent.KEYCODE_ENTER || event.keyCode == KeyEvent.KEYCODE_NUMPAD_ENTER || event.keyCode == KeyEvent.KEYCODE_TAB) {
            commitHidBuffer()
            return true
        }

        val ch = hidCharFor(event.keyCode)
        if (ch != null) {
            hidBuffer.append(ch)
        } else {
            hidBufferLooksLikeScan = false
        }
        return super.dispatchKeyEvent(event)
    }

    private fun commitHidBuffer() {
        val candidate = hidBuffer.toString()
        hidBuffer.clear()
        val wasQualified = hidBufferLooksLikeScan
        hidBufferLooksLikeScan = true
        if (!wasQualified || candidate.isEmpty()) return
        submitScan(candidate)
    }

    private fun submitScan(uid: String) {
        if (busy) return
        ScanHandler.handleScan(
            this, uid, smsBridge,
            onBusyChanged = { b ->
                mainHandler.post {
                    busy = b
                    readyText.text = if (b) "Reading card..." else "Ready to Scan"
                    scanIcon.text = if (b) "⏳" else "💳"
                }
            },
            onResult = { result -> mainHandler.post { showResult(result); refreshPendingCount() } },
        )
    }

    private fun showResult(result: ScanResult) {
        readyBlock.visibility = View.GONE
        resultBlock.visibility = View.VISIBLE

        val data = result.data
        val name = data?.optString("name", "")?.takeIf { it.isNotEmpty() }
        val role = data?.optString("role", "")?.takeIf { it.isNotEmpty() }
        val roleLabel = data?.optString("role_label", "")?.takeIf { it.isNotEmpty() }
        val className = data?.optString("class_name", "")?.takeIf { it.isNotEmpty() }
        val studentId = data?.optString("student_id", "")?.takeIf { it.isNotEmpty() }
        val fees = data?.optJSONObject("fees")
        val studentDva = data?.optJSONObject("student_dva")
        val isGood = result.outcome == ScanOutcome.WELCOME || result.outcome == ScanOutcome.GOODBYE
        val isTeacher = isGood && role != null && role != "student"

        val (title, colorRes, icon) = when (result.outcome) {
            ScanOutcome.WELCOME -> Triple("Welcome!", 0xFF4ADE80.toInt(), "✓")
            ScanOutcome.GOODBYE -> Triple("Goodbye!", 0xFF60A5FA.toInt(), "✓")
            ScanOutcome.INVALID -> Triple("Card Not Recognized", 0xFFF87171.toInt(), "✕")
            ScanOutcome.DUPLICATE -> Triple("Already Recorded", 0xFFFBBF24.toInt(), "⚠")
            ScanOutcome.ERROR -> Triple("Something Went Wrong", 0xFFF87171.toInt(), "✕")
        }
        resultTitle.text = title
        resultTitle.setTextColor(colorRes)
        resultIcon.text = icon
        resultIcon.setTextColor(colorRes)
        (resultIconBg.background.mutate() as android.graphics.drawable.GradientDrawable).setColor((colorRes and 0x00FFFFFF) or 0x33000000)

        if (name != null) {
            resultName.text = name
            resultName.visibility = View.VISIBLE
            val subtitle = when {
                isTeacher -> (roleLabel ?: role ?: "").uppercase()
                className != null || studentId != null -> listOfNotNull(className, studentId).joinToString(" · ")
                else -> null
            }
            if (subtitle != null && subtitle.isNotEmpty()) {
                resultSubtitle.text = subtitle
                resultSubtitle.visibility = View.VISIBLE
            } else {
                resultSubtitle.visibility = View.GONE
            }
            resultText.visibility = View.GONE
        } else {
            resultName.visibility = View.GONE
            resultSubtitle.visibility = View.GONE
            if (!result.message.isNullOrEmpty()) {
                resultText.text = result.message
                resultText.visibility = View.VISIBLE
            } else {
                resultText.visibility = View.GONE
            }
        }

        // Deliberately generic, never the student's name - spoken aloud on a
        // shared kiosk is a privacy concern the school flagged.
        val spoken = when (result.outcome) {
            ScanOutcome.WELCOME -> "Welcome."
            ScanOutcome.GOODBYE -> "Goodbye."
            ScanOutcome.INVALID -> "This card is not registered."
            ScanOutcome.DUPLICATE -> "Attendance has already been recorded."
            ScanOutcome.ERROR -> "Unable to record attendance. Please try again."
        }
        tts?.speak(spoken, TextToSpeech.QUEUE_FLUSH, null, null)

        if (fees != null) {
            val paid = fees.opt("paid")?.toString() ?: "0"
            val outstanding = fees.opt("outstanding")?.toString() ?: "0"
            feePaidText.text = "Fees Paid: ₦$paid"
            feeOutstandingText.text = "Outstanding: ₦$outstanding"
            if (studentDva != null) {
                val bank = studentDva.optString("bank_name", "")
                val account = studentDva.optString("account_number", "")
                val accountName = studentDva.optString("account_name", "")
                feeDvaText.text = if (accountName.isNotEmpty()) "$bank · $account\n$accountName" else "$bank · $account"
                feeDvaText.visibility = View.VISIBLE
            } else {
                feeDvaText.visibility = View.GONE
            }
            currentFeeContext = FeeContext(
                studentId = data?.optString("id", "") ?: "",
                name = name ?: "",
                className = className ?: "",
                paid = paid,
                outstanding = outstanding,
                dva = studentDva,
            )
            feeCard.visibility = View.VISIBLE
        } else {
            feeCard.visibility = View.GONE
            currentFeeContext = null
        }

        resetResultRunnable?.let { mainHandler.removeCallbacks(it) }
        val hasFees = fees != null
        val displayMs = if (hasFees) 15_000L else 4_000L
        val runnable = Runnable {
            readyBlock.visibility = View.VISIBLE
            resultBlock.visibility = View.GONE
        }
        resetResultRunnable = runnable
        mainHandler.postDelayed(runnable, displayMs)
    }

    private fun onPrintTapped() {
        val ctx = currentFeeContext ?: return
        printerBridge.printFeeReminder(
            schoolName = KioskStore.schoolName(this) ?: "SchoolDom",
            studentName = ctx.name,
            studentClass = ctx.className,
            studentId = ctx.studentId,
            paid = "₦${ctx.paid}",
            outstanding = "₦${ctx.outstanding}",
            accountNumber = ctx.dva?.optString("account_number", "") ?: "",
            bankName = ctx.dva?.optString("bank_name", "") ?: "",
            accountName = ctx.dva?.optString("account_name", "") ?: "",
            dateText = java.text.SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.US).format(java.util.Date()),
        ) { ok, error ->
            mainHandler.post {
                Toast.makeText(this, if (ok) "Printed." else "Could not print: ${error ?: "unknown error"}", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun onSendSmsTapped() {
        val ctx = currentFeeContext ?: return
        if (ctx.studentId.isEmpty()) return
        bgExecutor.execute {
            try {
                GateEndpoints.sendFeeReminder(this, ctx.studentId)
                mainHandler.post { Toast.makeText(this, "Fee reminder sent.", Toast.LENGTH_SHORT).show() }
            } catch (e: Exception) {
                mainHandler.post { Toast.makeText(this, "Could not send: ${e.message}", Toast.LENGTH_SHORT).show() }
            }
        }
    }

    // ---------------------------------------------------------------- Gate settings

    private fun loadGateSettings() {
        bgExecutor.execute {
            try {
                val res = GateEndpoints.loadGateSettings(this)
                val data = res.optJSONObject("data") ?: return@execute
                val seconds = data.optInt("duplicate_protection_seconds", -1)
                if (seconds > 0) ScanHandler.cooldownSeconds = seconds
                GateSettingsCache.save(this, data)
            } catch (e: Exception) {
                // Keep the default (and whatever was cached last time) - a
                // settings-fetch failure shouldn't block scanning.
            }
        }
    }

    // ---------------------------------------------------------------- Heartbeat

    private fun sendHeartbeat() {
        if (heartbeatInFlight) return
        heartbeatInFlight = true
        bgExecutor.execute {
            val outcome = Heartbeat.send(this, synced = pendingCount == 0)
            mainHandler.post {
                heartbeatInFlight = false
                online = outcome.online
                updateStatusText()
                if (!outcome.authorized) {
                    handleRemoteRevocation()
                    return@post
                }
                if (outcome.schoolName != null) {
                    schoolNameText.text = outcome.schoolName
                }
                if (outcome.online) refreshContactsIfStale()
            }
            refreshPendingCount()
        }
    }

    private fun refreshContactsIfStale() {
        val last = contactsRefreshedAt
        if (contactsRefreshing) return
        if (last != null && System.currentTimeMillis() - last < contactsRefreshIntervalMs) return
        contactsRefreshing = true
        bgExecutor.execute {
            val ok = GuardianContactsCache.refresh(this)
            if (ok) contactsRefreshedAt = System.currentTimeMillis()
            contactsRefreshing = false
        }
    }

    private fun refreshPendingCount() {
        val result = ApiClient.replayOfflineQueue(this)
        mainHandler.post {
            pendingCount = result.remaining
            sessionExpired = result.sessionExpired
            updateStatusText()
        }
    }

    private fun updateStatusText() {
        val parts = mutableListOf<String>()
        parts.add(if (online) "Online" else "Offline")
        if (pendingCount > 0) {
            parts.add(if (sessionExpired) "$pendingCount pending - tap Re-enter key" else "$pendingCount pending")
        }
        statusText.text = parts.joinToString("  ·  ")
        statusDot.backgroundTintList = android.content.res.ColorStateList.valueOf(
            getColor(if (online) R.color.success else R.color.danger),
        )
    }

    private fun handleRemoteRevocation() {
        SessionStore.clearSession(this)
        KioskStore.deactivate(this)
        startActivity(Intent(this, MainActivity::class.java))
        finish()
    }

    private fun confirmReProvision() {
        AlertDialog.Builder(this)
            .setTitle("Re-enter license key?")
            .setMessage(
                "This deactivates this terminal's current registration and returns to the activation screen. " +
                    "Use this if the wrong key was entered, or the device is stuck waiting for a school assignment.",
            )
            .setNegativeButton("Cancel", null)
            .setPositiveButton("Continue") { _, _ ->
                SessionStore.clearSession(this)
                KioskStore.deactivate(this)
                startActivity(Intent(this, MainActivity::class.java))
                finish()
            }
            .show()
    }
}
