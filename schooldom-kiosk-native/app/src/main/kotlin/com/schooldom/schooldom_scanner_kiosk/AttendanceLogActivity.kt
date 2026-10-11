package com.schooldom.schooldom_scanner_kiosk

import android.app.Activity
import android.app.AlertDialog
import android.os.Bundle
import android.view.View
import android.widget.ArrayAdapter
import android.widget.ListView
import android.widget.TextView

/**
 * Settings screen's "Today's Attendance Log" - read-only view of
 * AttendanceLogStore's same-day record of who has clocked in/out on this
 * terminal. Same stock ListView/ArrayAdapter approach as SmsInboxActivity;
 * this is a small, occasionally-opened admin screen, not worth a custom
 * adapter for.
 */
class AttendanceLogActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_attendance_log)
        findViewById<View>(R.id.backButton).setOnClickListener { finish() }
        findViewById<View>(R.id.clearButton).setOnClickListener { confirmClear() }
        displayLog()
    }

    private fun displayLog() {
        val listView = findViewById<ListView>(R.id.logListView)
        val emptyText = findViewById<TextView>(R.id.logEmptyText)
        val entries = AttendanceLogStore.readToday(this)

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
            val subtitle = listOfNotNull(detail.takeIf { it.isNotEmpty() }, outcome).joinToString(" · ")
            "$name  •  $time\n$subtitle"
        }
        listView.adapter = ArrayAdapter(this, android.R.layout.simple_list_item_1, items)
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
