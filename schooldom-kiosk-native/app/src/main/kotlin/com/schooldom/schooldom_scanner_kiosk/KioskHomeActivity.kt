package com.schooldom.schooldom_scanner_kiosk

import android.app.Activity
import android.nfc.NfcAdapter
import android.nfc.Tag
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.tts.TextToSpeech
import android.view.KeyEvent
import android.view.WindowManager
import android.widget.TextView
import java.util.Locale

/**
 * Direct (partial - see rewrite scope) port of kiosk_home_screen.dart: NFC
 * tap reading, the external USB HID keyboard-wedge reader path (same
 * inter-keystroke-timing technique as HidRfidReader.cs), scan submission via
 * ScanHandler, and TTS feedback. NOT YET PORTED: heartbeat (battery/location
 * reporting), receipt printing on the result screen, gate settings, the
 * self-update prompt, and the richer offline/SMS-fallback branch (see
 * ScanHandler's doc comment). Each is a tracked follow-up, not silently
 * dropped.
 */
class KioskHomeActivity : Activity(), NfcAdapter.ReaderCallback {
    private lateinit var printerBridge: TopwisePrinterBridge
    private lateinit var smsBridge: LocalSmsBridge
    private var tts: TextToSpeech? = null
    private var nfcAdapter: NfcAdapter? = null
    private val mainHandler = Handler(Looper.getMainLooper())

    private lateinit var readyText: TextView
    private lateinit var resultText: TextView
    private var busy = false
    private var resetResultRunnable: Runnable? = null

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

        readyText = findViewById(R.id.readyText)
        resultText = findViewById(R.id.resultText)
        findViewById<TextView>(R.id.schoolNameText).text =
            KioskStore.schoolName(this) ?: "Waiting for school assignment"

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
            this, uid,
            onBusyChanged = { b -> mainHandler.post { busy = b } },
            onResult = { result -> mainHandler.post { showResult(result) } },
        )
    }

    private fun showResult(result: ScanResult) {
        readyText.visibility = android.view.View.GONE
        resultText.visibility = android.view.View.VISIBLE
        // Deliberately generic, never the student's name - spoken aloud on a
        // shared kiosk is a privacy concern the school flagged.
        val spoken = when (result.outcome) {
            ScanOutcome.WELCOME -> "Welcome."
            ScanOutcome.GOODBYE -> "Goodbye."
            ScanOutcome.INVALID -> "This card is not registered."
            ScanOutcome.DUPLICATE -> "Attendance has already been recorded."
            ScanOutcome.ERROR -> "Unable to record attendance. Please try again."
        }
        resultText.text = result.message ?: spoken
        tts?.speak(spoken, TextToSpeech.QUEUE_FLUSH, null, null)

        resetResultRunnable?.let { mainHandler.removeCallbacks(it) }
        val hasFees = result.data?.has("fees") == true && !result.data.isNull("fees")
        val displayMs = if (hasFees) 15_000L else 4_000L
        val runnable = Runnable {
            readyText.visibility = android.view.View.VISIBLE
            resultText.visibility = android.view.View.GONE
        }
        resetResultRunnable = runnable
        mainHandler.postDelayed(runnable, displayMs)
    }
}
