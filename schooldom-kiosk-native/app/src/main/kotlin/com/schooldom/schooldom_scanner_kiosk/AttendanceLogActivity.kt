package com.schooldom.schooldom_scanner_kiosk

import android.app.Activity
import android.app.AlertDialog
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.View
import android.widget.ArrayAdapter
import android.widget.ListView
import android.widget.TextView
import android.widget.Toast
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Locale

/**
 * Settings screen's "Today's Attendance Log" - read-only view of
 * AttendanceLogStore's same-day record of who has clocked in/out on this
 * terminal. Same stock ListView/ArrayAdapter approach as SmsInboxActivity;
 * this is a small, occasionally-opened admin screen, not worth a custom
 * adapter for.
 *
 * An entry carries a "fees" snapshot only when it was recorded while the
 * terminal was in Fee Tracker mode (see KioskHomeActivity.showResult) -
 * tapping that entry offers the same Print Receipt/Send SMS actions the
 * main scan screen shows right after a tap, so finance staff don't need
 * the student to tap their card again just to get a receipt.
 */
class AttendanceLogActivity : Activity() {
    private var entries: List<JSONObject> = emptyList()
    private val mainHandler = Handler(Looper.getMainLooper())
    private lateinit var printerBridge: TopwisePrinterBridge

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_attendance_log)
        printerBridge = TopwisePrinterBridge(applicationContext)
        findViewById<View>(R.id.backButton).setOnClickListener { finish() }
        findViewById<View>(R.id.clearButton).setOnClickListener { confirmClear() }
        displayLog()
    }

    private fun displayLog() {
        val listView = findViewById<ListView>(R.id.logListView)
        val emptyText = findViewById<TextView>(R.id.logEmptyText)
        entries = AttendanceLogStore.readToday(this)

        if (entries.isEmpty()) {
            emptyText.visibility = View.VISIBLE
            listView.visibility = View.GONE
            return
        }

        emptyText.visibility = View.GONE
        listView.visibility = View.VISIBLE
        val items = entries.map { entry ->
            val name = entry.optString("name", "Unknown")
            val detail = entry.optString("detail", "")
            val outcome = entry.optString("outcome", "")
            val time = entry.optString("time", "")
            val hasFees = entry.has("fees")
            val subtitle = listOfNotNull(detail.takeIf { it.isNotEmpty() }, outcome).joinToString(" · ")
            val hint = if (hasFees) "\nTap for receipt/SMS options" else ""
            "$name  •  $time\n$subtitle$hint"
        }
        listView.adapter = ArrayAdapter(this, R.layout.list_item_light_text, items)
        listView.setOnItemClickListener { _, _, position, _ ->
            val entry = entries.getOrNull(position) ?: return@setOnItemClickListener
            val fees = entry.optJSONObject("fees")
            if (fees != null) showFeeActions(entry, fees)
        }
    }

    private fun showFeeActions(entry: JSONObject, fees: JSONObject) {
        AlertDialog.Builder(this)
            .setTitle(entry.optString("name", "Student"))
            .setPositiveButton("Print Receipt") { _, _ -> printReceipt(entry, fees) }
            .setNegativeButton("Send SMS") { _, _ -> sendSms(fees) }
            .setNeutralButton("Cancel", null)
            .show()
    }

    private fun printReceipt(entry: JSONObject, fees: JSONObject) {
        val dva = fees.optJSONObject("student_dva")
        printerBridge.printFeeReminder(
            schoolName = KioskStore.schoolName(this) ?: "SchoolDom",
            studentName = entry.optString("name", ""),
            studentClass = fees.optString("class_name", ""),
            studentId = fees.optString("student_id", ""),
            paid = "₦${fees.optString("paid", "0")}",
            outstanding = "₦${fees.optString("outstanding", "0")}",
            accountNumber = dva?.optString("account_number", "") ?: "",
            bankName = dva?.optString("bank_name", "") ?: "",
            accountName = dva?.optString("account_name", "") ?: "",
            dateText = SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.US).format(java.util.Date()),
        ) { ok, error ->
            mainHandler.post {
                Toast.makeText(this, if (ok) "Printed." else "Could not print: ${error ?: "unknown error"}", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun sendSms(fees: JSONObject) {
        val userId = fees.optString("user_id", "")
        if (userId.isEmpty()) {
            Toast.makeText(this, "Missing student record - can't send SMS.", Toast.LENGTH_SHORT).show()
            return
        }
        Thread {
            try {
                GateEndpoints.sendFeeReminder(this, userId)
                mainHandler.post { Toast.makeText(this, "Fee reminder sent.", Toast.LENGTH_SHORT).show() }
            } catch (e: Exception) {
                mainHandler.post { Toast.makeText(this, "Could not send: ${e.message}", Toast.LENGTH_SHORT).show() }
            }
        }.start()
    }

    private fun confirmClear() {
        AlertDialog.Builder(this)
            .setTitle("Clear today's log?")
            .setMessage("This only clears what's shown on this terminal - it does not affect attendance already recorded on the server.")
            .setNegativeButton("Cancel", null)
            .setPositiveButton("Clear") { _, _ ->
                AttendanceLogStore.clear(this)
                displayLog()
            }
            .show()
    }
}
