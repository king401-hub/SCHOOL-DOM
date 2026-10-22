package com.schooldom.schooldom_scanner_kiosk

import android.app.Activity
import android.app.TimePickerDialog
import android.content.Intent
import android.nfc.NfcAdapter
import android.os.Bundle
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.RadioGroup
import android.widget.TextView
import android.widget.Toast
import org.json.JSONObject
import java.util.Locale
import java.util.concurrent.Executors

/**
 * Direct port of GateSettingsScreen in gate_settings_screen.dart - Operating
 * Mode, Attendance Schedule, duplicate-tap protection, and device status,
 * reached via GatePinActivity. NOT YET PORTED: changing the PIN itself
 * (setGatePin) - a separate follow-up, same as the rest of this app's
 * tracked gaps.
 */
class GateSettingsActivity : Activity() {
    private val worker = Executors.newSingleThreadExecutor()

    private data class TimeRow(val container: View, val label: TextView, val value: TextView, var hour: Int, var minute: Int, val title: String)

    private lateinit var rows: Map<String, TimeRow>
    private lateinit var modeGroup: RadioGroup
    private lateinit var duplicateSecondsInput: EditText
    private lateinit var saveButton: Button
    private lateinit var settingsBusy: ProgressBar
    private lateinit var settingsScroll: View

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_gate_settings)

        findViewById<View>(R.id.backButton).setOnClickListener { finish() }

        settingsBusy = findViewById(R.id.settingsBusy)
        settingsScroll = findViewById(R.id.settingsScroll)
        modeGroup = findViewById(R.id.modeGroup)
        duplicateSecondsInput = findViewById(R.id.duplicateSecondsInput)
        saveButton = findViewById(R.id.saveButton)

        rows = mapOf(
            "early_start" to timeRow(R.id.rowEarlyStart, "Clock-in start", 7, 30),
            "early_end" to timeRow(R.id.rowEarlyEnd, "Clock-in end", 10, 0),
            "clockout_start" to timeRow(R.id.rowClockoutStart, "Clock-out start", 13, 0),
            "clockout_end" to timeRow(R.id.rowClockoutEnd, "Clock-out end", 16, 0),
        )
        rows.values.forEach { row ->
            row.label.text = row.title
            refreshRowDisplay(row)
            row.container.setOnClickListener { pickTime(row) }
        }

        setStatusRow(R.id.rowNetworkStatus, "Network", "Checked live on home screen", android.R.color.darker_gray)
        setStatusRow(R.id.rowNfcStatus, "NFC/RFID Reader", "Checking...", android.R.color.darker_gray)
        setStatusRow(R.id.rowPrinterStatus, "Thermal Printer", "Checking...", android.R.color.darker_gray)
        // onResume (always called right after onCreate too) does the actual
        // check, so it also re-runs every time this screen is returned to.

        saveButton.setOnClickListener { save() }
        findViewById<Button>(R.id.ussdButton).setOnClickListener {
            startActivity(Intent(this, UssdActivity::class.java))
        }
        findViewById<Button>(R.id.smsInboxButton).setOnClickListener {
            startActivity(Intent(this, SmsInboxActivity::class.java))
        }
        findViewById<Button>(R.id.attendanceLogButton).setOnClickListener {
            startActivity(Intent(this, AttendanceLogActivity::class.java))
        }

        load()
    }

    override fun onResume() {
        super.onResume()
        // checkDeviceStatus only ran once, in onCreate - reopening this
        // screen after toggling NFC in the system Settings app (leave,
        // flip the switch, come back) kept showing whatever it read the
        // first time, not what's actually on now.
        checkDeviceStatus()
    }

    private fun timeRow(containerId: Int, title: String, defaultHour: Int, defaultMinute: Int): TimeRow {
        val container = findViewById<View>(containerId)
        val label = container.findViewById<TextView>(R.id.rowLabel)
        val value = container.findViewById<TextView>(R.id.rowValue)
        return TimeRow(container, label, value, defaultHour, defaultMinute, title)
    }

    private fun refreshRowDisplay(row: TimeRow) {
        val cal = java.util.Calendar.getInstance().apply {
            set(java.util.Calendar.HOUR_OF_DAY, row.hour)
            set(java.util.Calendar.MINUTE, row.minute)
        }
        row.value.text = java.text.SimpleDateFormat("h:mm a", Locale.US).format(cal.time)
    }

    private fun pickTime(row: TimeRow) {
        TimePickerDialog(this, { _, h, m ->
            row.hour = h
            row.minute = m
            refreshRowDisplay(row)
        }, row.hour, row.minute, false).show()
    }

    private fun setStatusRow(containerId: Int, label: String, status: String, colorRes: Int) {
        val container = findViewById<View>(containerId)
        container.findViewById<TextView>(R.id.rowLabel).text = label
        val valueView = container.findViewById<TextView>(R.id.rowValue)
        valueView.text = status
        valueView.setTextColor(getColor(colorRes))
    }

    private fun checkDeviceStatus() {
        val nfcAvailable = NfcAdapter.getDefaultAdapter(this)?.isEnabled == true
        setStatusRow(
            R.id.rowNfcStatus, "NFC/RFID Reader",
            if (nfcAvailable) "Connected" else "Not detected",
            if (nfcAvailable) R.color.success else R.color.danger,
        )
        TopwisePrinterBridge(applicationContext).isAvailable { ok ->
            runOnUiThread {
                setStatusRow(
                    R.id.rowPrinterStatus, "Thermal Printer",
                    if (ok) "Connected" else "Not detected",
                    if (ok) R.color.success else R.color.danger,
                )
            }
        }
    }

    private fun parseTime(raw: String): Pair<Int, Int>? {
        val parts = raw.split(":")
        if (parts.size < 2) return null
        val h = parts[0].toIntOrNull() ?: return null
        val m = parts[1].toIntOrNull() ?: return null
        return h to m
    }

    private fun formatForApi(hour: Int, minute: Int): String =
        String.format(Locale.US, "%02d:%02d", hour, minute)

    /** Renders whatever the server most recently said the settings are -
     * called after both a fresh load and a successful save, so a save is
     * always confirmed against the real post-save server state rather than
     * just echoing back what the admin typed. Must run on the UI thread. */
    private fun applySettingsData(data: JSONObject) {
        val mode = data.optString("mode", "attendance_only")
        if (mode == "fee_tracker") {
            (findViewById<View>(R.id.modeFeeTracker) as android.widget.RadioButton).isChecked = true
        } else {
            (findViewById<View>(R.id.modeAttendanceOnly) as android.widget.RadioButton).isChecked = true
        }
        duplicateSecondsInput.setText(data.optInt("duplicate_protection_seconds", 30).toString())
        for ((key, row) in rows) {
            val parsed = parseTime(data.optString(key, ""))
            if (parsed != null) {
                row.hour = parsed.first
                row.minute = parsed.second
                refreshRowDisplay(row)
            }
        }
    }

    private fun load() {
        settingsBusy.visibility = View.VISIBLE
        settingsScroll.visibility = View.GONE
        worker.execute {
            try {
                val res = GateEndpoints.loadGateSettings(this)
                val data = res.optJSONObject("data") ?: JSONObject()
                runOnUiThread {
                    applySettingsData(data)
                    settingsBusy.visibility = View.GONE
                    settingsScroll.visibility = View.VISIBLE
                }
            } catch (e: Exception) {
                runOnUiThread {
                    settingsBusy.visibility = View.GONE
                    settingsScroll.visibility = View.VISIBLE
                    Toast.makeText(this, "Could not load settings: ${e.message}", Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    private fun save() {
        val mode = if (modeGroup.checkedRadioButtonId == R.id.modeFeeTracker) "fee_tracker" else "attendance_only"
        val duplicateSeconds = duplicateSecondsInput.text.toString().toIntOrNull() ?: 30
        val fields = JSONObject().apply {
            put("mode", mode)
            for ((key, row) in rows) put(key, formatForApi(row.hour, row.minute))
            put("duplicate_protection_seconds", duplicateSeconds)
        }
        saveButton.isEnabled = false
        worker.execute {
            try {
                val res = GateEndpoints.updateGateSettings(this, fields)
                val data = res.optJSONObject("data") ?: JSONObject()
                GateSettingsCache.save(this, data)
                val seconds = data.optInt("duplicate_protection_seconds", -1)
                if (seconds > 0) ScanHandler.cooldownSeconds = seconds
                runOnUiThread {
                    // Re-render from exactly what the server just echoed back,
                    // not from local state - the only real proof a save took
                    // is the canonical post-save value, not an optimistic
                    // assumption that what was sent is what got stored.
                    applySettingsData(data)
                    saveButton.isEnabled = true
                    Toast.makeText(this, "Settings saved.", Toast.LENGTH_SHORT).show()
                }
            } catch (e: Exception) {
                runOnUiThread {
                    saveButton.isEnabled = true
                    Toast.makeText(this, "Could not save: ${e.message}", Toast.LENGTH_LONG).show()
                }
            }
        }
    }
}
