package com.schooldom.schooldom_scanner_kiosk

import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.nfc.NfcAdapter
import android.nfc.Tag
import android.content.Context
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.PowerManager
import android.speech.tts.TextToSpeech
import android.view.KeyEvent
import android.view.View
import android.view.WindowManager
import android.graphics.Outline
import android.view.ViewOutlineProvider
import android.widget.Button
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import org.json.JSONObject
import java.io.File
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
    private var wakeLock: PowerManager.WakeLock? = null
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
    private lateinit var resultPhoto: ImageView
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
    private var photoRequestId = 0

    // ---- Heartbeat / connectivity state (mirrors kiosk_home_screen.dart) ----
    private val heartbeatIntervalMs = 5 * 60 * 1000L
    private val contactsRefreshIntervalMs = 30 * 60 * 1000L
    private var heartbeatInFlight = false
    private var online = true
    private var pendingCount = 0
    private var sessionExpired = false
    private var contactsRefreshedAt: Long? = null
    private var promptedUpdateCode: Int? = null
    private var downloadingUpdate = false
    private var updateDialogOpen = false
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
        val userId: String,
        val displayStudentId: String,
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

        // Belt-and-suspenders against the screen sleeping: FLAG_KEEP_SCREEN_ON
        // above is the normal, recommended way, but some POS/kiosk vendor ROMs
        // apply their own idle-screen-off power policy that ignores it (seen
        // on the T2N hardware - dumpsys power showed the device fully asleep,
        // Display Power: state=OFF, with zero active wake locks, despite this
        // Activity being alive and resumed the whole time). NFC reader-mode
        // polling stops entirely whenever the screen sleeps, so this is not
        // just a cosmetic issue - it silently breaks scanning. A real
        // PowerManager wake lock operates at the OS power-manager level
        // rather than as a window attribute, which these vendor policies are
        // far less likely to override.
        @Suppress("DEPRECATION")
        wakeLock = (getSystemService(Context.POWER_SERVICE) as PowerManager).newWakeLock(
            PowerManager.SCREEN_BRIGHT_WAKE_LOCK or PowerManager.ON_AFTER_RELEASE,
            "SchoolDomKiosk:ScanningScreen",
        )
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
        resultPhoto = findViewById(R.id.resultPhoto)
        resultPhoto.clipToOutline = true
        resultPhoto.outlineProvider = object : ViewOutlineProvider() {
            override fun getOutline(view: View, outline: Outline) {
                outline.setOval(0, 0, view.width, view.height)
            }
        }
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
        wakeLock?.let { if (!it.isHeld) it.acquire(24 * 60 * 60 * 1000L) }
    }

    override fun onPause() {
        super.onPause()
        nfcAdapter?.disableReaderMode(this)
        wakeLock?.let { if (it.isHeld) it.release() }
    }

    override fun onDestroy() {
        super.onDestroy()
        wakeLock?.let { if (it.isHeld) it.release() }
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

        // A recognized person's own photo reads far better at a glance than a
        // generic checkmark - falls back to the icon circle above whenever
        // there's no photo on file, or the scan wasn't a real match.
        resultPhoto.visibility = View.GONE
        resultIconBg.visibility = View.VISIBLE
        resultIcon.visibility = View.VISIBLE
        val photoUrl = data?.optString("photo_url", "")?.takeIf { it.isNotEmpty() }
        if (isGood && name != null && photoUrl != null) {
            val requestId = ++photoRequestId
            bgExecutor.execute {
                val bitmap = ImageLoader.fetch(this, photoUrl)
                mainHandler.post {
                    if (bitmap != null && requestId == photoRequestId) {
                        resultPhoto.setImageBitmap(bitmap)
                        resultPhoto.visibility = View.VISIBLE
                        resultIconBg.visibility = View.GONE
                        resultIcon.visibility = View.GONE
                    }
                }
            }
        }

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
                userId = data?.optString("id", "") ?: "",
                displayStudentId = studentId ?: "",
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
        val displayMs = if (hasFees) 15_000L else 6_000L
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
            studentId = ctx.displayStudentId,
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
        if (ctx.userId.isEmpty()) return
        bgExecutor.execute {
            try {
                GateEndpoints.sendFeeReminder(this, ctx.userId)
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
                if (outcome.updateAvailable) maybePromptForUpdate(outcome)
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

    // ---------------------------------------------------------------- Self-update

    /** Pops the "update available" question up on its own the first time a
     * heartbeat reports a newer build after launch, instead of leaving it to
     * a tiny icon nobody notices. Held back while a card is being read, a
     * result is showing, or settings are open; the next heartbeat (5 min)
     * tries again. */
    private fun maybePromptForUpdate(outcome: HeartbeatOutcome) {
        val code = outcome.latestVersionCode ?: return
        if (promptedUpdateCode == code) return
        if (busy || downloadingUpdate || updateDialogOpen) return
        if (resultBlock.visibility == View.VISIBLE) return
        promptedUpdateCode = code
        showUpdateDialog(outcome)
    }

    private fun showUpdateDialog(info: HeartbeatOutcome) {
        if (updateDialogOpen) return
        updateDialogOpen = true
        val notes = info.releaseNotes?.trim().takeIf { !it.isNullOrEmpty() } ?: "A newer version of this app is available."
        AlertDialog.Builder(this)
            .setTitle("Update available - ${info.latestVersionName ?: ""}")
            .setMessage(notes)
            .setOnDismissListener { updateDialogOpen = false }
            .setNegativeButton("Later", null)
            .setPositiveButton("Install Now") { _, _ -> installUpdate(info) }
            .show()
    }

    private fun installUpdate(info: HeartbeatOutcome) {
        val apkUrl = info.apkUrl ?: return
        val versionCode = info.latestVersionCode ?: System.currentTimeMillis().toInt()

        val dialogView = layoutInflater.inflate(R.layout.dialog_update_progress, null)
        val statusText = dialogView.findViewById<TextView>(R.id.updateStatusText)
        val progressBar = dialogView.findViewById<android.widget.ProgressBar>(R.id.updateProgressBar)
        val percentText = dialogView.findViewById<TextView>(R.id.updatePercentText)
        val cancelButton = dialogView.findViewById<Button>(R.id.updateCancelButton)

        var cancelled = false
        val dialog = AlertDialog.Builder(this)
            .setView(dialogView)
            .setCancelable(false)
            .create()
        cancelButton.setOnClickListener {
            cancelled = true
            downloadingUpdate = false
            dialog.dismiss()
        }
        dialog.show()
        downloadingUpdate = true

        bgExecutor.execute {
            try {
                val dest = File(cacheDir, "schooldom-kiosk-update-$versionCode.apk")
                val file = AppUpdater.download(this, apkUrl, dest) { received, total ->
                    if (cancelled) return@download
                    mainHandler.post {
                        if (total != null && total > 0) {
                            val pct = (received * 100L / total).toInt()
                            progressBar.progress = pct
                            percentText.text = "$pct%"
                        } else {
                            percentText.text = "${received / 1024} KB"
                        }
                    }
                }
                if (cancelled) return@execute
                mainHandler.post {
                    statusText.text = "Opening installer..."
                    downloadingUpdate = false
                    dialog.dismiss()
                    openInstaller(file)
                }
            } catch (e: Exception) {
                if (cancelled) return@execute
                mainHandler.post {
                    downloadingUpdate = false
                    dialog.dismiss()
                    Toast.makeText(this, "Update failed: ${e.message}", Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    /** Hands the APK to Android's own package installer - the OS shows its
     * standard "install this app?" prompt (and, the very first time, an
     * "allow installs from this app" permission screen). Never installs
     * anything silently. Uses a plain file:// Uri (no AndroidX, so no
     * FileProvider available - see app/build.gradle.kts) with the matching
     * StrictMode exemption; acceptable for a closed kiosk fleet we control. */
    private fun openInstaller(file: File) {
        try {
            android.os.StrictMode.setVmPolicy(android.os.StrictMode.VmPolicy.Builder().build())
            val intent = Intent(Intent.ACTION_VIEW).apply {
                setDataAndType(android.net.Uri.fromFile(file), "application/vnd.android.package-archive")
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
            startActivity(intent)
        } catch (e: Exception) {
            Toast.makeText(this, "Could not open the installer: ${e.message}", Toast.LENGTH_LONG).show()
        }
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
