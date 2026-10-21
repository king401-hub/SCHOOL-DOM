package com.schooldom.cardassign

import android.app.Activity
import android.content.Intent
import android.nfc.NfcAdapter
import android.nfc.Tag
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.view.View
import android.widget.Button
import android.widget.ProgressBar
import android.widget.TextView
import org.json.JSONObject
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

/**
 * The actual "tap the card" screen. NFC reader-mode setup here is copied
 * verbatim from schooldom-kiosk-native's KioskHomeActivity - same flags,
 * same onResume/onPause lifecycle, same hex-UID format - because a card
 * assigned here has to match the UID the kiosk's own attendance scanner
 * reads off the same physical card later.
 */
class TapAssignActivity : Activity(), NfcAdapter.ReaderCallback {
    private val bgExecutor = Executors.newSingleThreadExecutor()
    private val mainHandler = Handler(Looper.getMainLooper())
    private var nfcAdapter: NfcAdapter? = null
    private val acceptingTaps = AtomicBoolean(true)

    private lateinit var backButton: TextView
    private lateinit var personNameText: TextView
    private lateinit var personSubtitleText: TextView
    private lateinit var statusText: TextView
    private lateinit var openNfcSettingsButton: Button
    private lateinit var cardUidText: TextView
    private lateinit var resultText: TextView
    private lateinit var forceAssignButton: Button
    private lateinit var tryAgainButton: Button
    private lateinit var assignAnotherButton: Button
    private lateinit var progressBar: ProgressBar

    private lateinit var personId: String
    private lateinit var personName: String
    private var pendingUid: String? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_tap_assign)

        personId = intent.getStringExtra("person_id") ?: ""
        personName = intent.getStringExtra("person_name") ?: "Student"
        val className = intent.getStringExtra("class_name") ?: ""
        val roleLabel = intent.getStringExtra("role_label") ?: ""
        val hasActiveCard = intent.getBooleanExtra("has_active_card", false)

        backButton = findViewById(R.id.backButton)
        personNameText = findViewById(R.id.personNameText)
        personSubtitleText = findViewById(R.id.personSubtitleText)
        statusText = findViewById(R.id.statusText)
        openNfcSettingsButton = findViewById(R.id.openNfcSettingsButton)
        cardUidText = findViewById(R.id.cardUidText)
        resultText = findViewById(R.id.resultText)
        forceAssignButton = findViewById(R.id.forceAssignButton)
        tryAgainButton = findViewById(R.id.tryAgainButton)
        assignAnotherButton = findViewById(R.id.assignAnotherButton)
        progressBar = findViewById(R.id.progressBar)

        personNameText.text = personName
        val subtitleParts = mutableListOf<String>()
        if (className.isNotEmpty()) subtitleParts.add(className) else if (roleLabel.isNotEmpty()) subtitleParts.add(roleLabel)
        if (hasActiveCard) subtitleParts.add("Already has a card - tapping a new one will replace it")
        personSubtitleText.text = subtitleParts.joinToString(" · ")

        nfcAdapter = NfcAdapter.getDefaultAdapter(this)

        backButton.setOnClickListener { finish() }
        tryAgainButton.setOnClickListener { resetToWaiting() }
        assignAnotherButton.setOnClickListener { finish() }
        forceAssignButton.setOnClickListener {
            pendingUid?.let { uid -> submitAssign(uid, force = true) }
        }
        openNfcSettingsButton.setOnClickListener {
            startActivity(Intent(Settings.ACTION_NFC_SETTINGS))
        }
    }

    /**
     * enableReaderMode() requires NFC to be switched on in system Settings -
     * when it's off, it doesn't error, it just never detects a tap, which
     * looks identical to a broken reader from the admin's seat ("nothing
     * happens"). Checked on every resume, not just once, since this is
     * exactly the kind of thing an admin backgrounds the app to go fix.
     */
    override fun onResume() {
        super.onResume()
        val adapter = nfcAdapter
        if (adapter == null) {
            statusText.text = "This device has no NFC reader."
            openNfcSettingsButton.visibility = View.GONE
            return
        }
        if (!adapter.isEnabled) {
            statusText.text = "NFC is turned off on this device - turn it on to read a card."
            openNfcSettingsButton.visibility = View.VISIBLE
            return
        }
        openNfcSettingsButton.visibility = View.GONE
        if (pendingUid == null && resultText.visibility != View.VISIBLE) {
            statusText.text = "Hold the card against the reader"
        }
        adapter.enableReaderMode(
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

    /** NfcAdapter.ReaderCallback - fires on a background thread. */
    override fun onTagDiscovered(tag: Tag) {
        if (!acceptingTaps.compareAndSet(true, false)) return
        val uid = tag.id?.joinToString("") { "%02X".format(it) }
        if (uid.isNullOrEmpty()) {
            acceptingTaps.set(true)
            return
        }
        mainHandler.post {
            pendingUid = uid
            cardUidText.text = "Card $uid"
            cardUidText.visibility = View.VISIBLE
            submitAssign(uid, force = false)
        }
    }

    private fun resetToWaiting() {
        pendingUid = null
        statusText.text = "Hold the card against the reader"
        cardUidText.visibility = View.GONE
        resultText.visibility = View.GONE
        forceAssignButton.visibility = View.GONE
        tryAgainButton.visibility = View.GONE
        assignAnotherButton.visibility = View.GONE
        acceptingTaps.set(true)
    }

    private fun submitAssign(cardUid: String, force: Boolean) {
        statusText.text = "Assigning..."
        resultText.visibility = View.GONE
        forceAssignButton.visibility = View.GONE
        tryAgainButton.visibility = View.GONE
        progressBar.visibility = View.VISIBLE

        bgExecutor.execute {
            try {
                val schoolCode = CardAssignStore.schoolCode(this)
                val payload = JSONObject().apply {
                    put("person_id", personId)
                    put("card_uid", cardUid)
                    if (schoolCode.isNotEmpty()) put("school_code", schoolCode)
                    if (force) put("force", true)
                }
                val (status, data) = ApiClient.postJsonRaw(this, "/api/rfid/card-assignments/assign/", payload)
                mainHandler.post { handleAssignResponse(status, data, cardUid) }
            } catch (e: SessionExpiredException) {
                mainHandler.post {
                    CardAssignStore.clearAll(this)
                    finish()
                }
            } catch (e: Exception) {
                mainHandler.post {
                    progressBar.visibility = View.GONE
                    statusText.text = "Hold the card against the reader"
                    showResult(e.message ?: "Could not assign the card.", isError = true)
                    tryAgainButton.visibility = View.VISIBLE
                }
            }
        }
    }

    private fun handleAssignResponse(status: Int, data: JSONObject, cardUid: String) {
        progressBar.visibility = View.GONE
        if (status in 200..299 && data.optBoolean("success", false)) {
            statusText.text = "Card assigned"
            showResult("$personName is now linked to card $cardUid.", isError = false)
            assignAnotherButton.visibility = View.VISIBLE
            return
        }
        statusText.text = "Hold the card against the reader"
        if (status == 409 && data.optBoolean("conflict", false)) {
            showResult(data.optString("message", "This card or student already has an active link."), isError = true)
            forceAssignButton.visibility = View.VISIBLE
            tryAgainButton.visibility = View.VISIBLE
            return
        }
        showResult(data.optString("message", "Could not assign the card ($status)."), isError = true)
        tryAgainButton.visibility = View.VISIBLE
    }

    private fun showResult(message: String, isError: Boolean) {
        resultText.text = message
        resultText.setBackgroundColor(if (isError) 0xFF4A1414.toInt() else 0xFF123A1E.toInt())
        resultText.setTextColor(resources.getColor(if (isError) R.color.danger else R.color.success, theme))
        resultText.visibility = View.VISIBLE
    }
}
