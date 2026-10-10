package com.schooldom.schooldom_scanner_kiosk

import android.Manifest
import android.app.Activity
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.view.View
import android.widget.ArrayAdapter
import android.widget.ListView
import android.widget.TextView
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Settings screen's "Received Messages" - shows texts the terminal's own SIM
 * has received (mainly carrier balance/airtime alerts, same SIM
 * LocalSmsBridge sends the offline gate-SMS fallback from) without needing
 * to pull the SIM and check it in another phone. Read-only, newest first.
 * Uses the plain SMS content provider + a stock ArrayAdapter/system row
 * layout rather than a custom adapter - this is a small, infrequently-opened
 * diagnostic list, not worth any extra code for.
 */
class SmsInboxActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_sms_inbox)
        findViewById<View>(R.id.backButton).setOnClickListener { finish() }
        loadMessages()
    }

    private fun loadMessages() {
        if (checkSelfPermission(Manifest.permission.READ_SMS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.READ_SMS), REQUEST_READ_SMS)
            return
        }
        displayMessages()
    }

    private fun displayMessages() {
        val listView = findViewById<ListView>(R.id.smsListView)
        val emptyText = findViewById<TextView>(R.id.smsEmptyText)
        val items = mutableListOf<String>()

        try {
            val cursor = contentResolver.query(
                Uri.parse("content://sms/inbox"),
                arrayOf("address", "body", "date"),
                null, null,
                "date DESC",
            )
            cursor?.use {
                val addressIdx = it.getColumnIndex("address")
                val bodyIdx = it.getColumnIndex("body")
                val dateIdx = it.getColumnIndex("date")
                val formatter = SimpleDateFormat("MMM d, h:mm a", Locale.US)
                while (it.moveToNext() && items.size < 100) {
                    val address = (if (addressIdx >= 0) it.getString(addressIdx) else null) ?: "Unknown"
                    val body = (if (bodyIdx >= 0) it.getString(bodyIdx) else null) ?: ""
                    val dateText = if (dateIdx >= 0) formatter.format(Date(it.getLong(dateIdx))) else ""
                    items.add("$address  •  $dateText\n$body")
                }
            }
        } catch (e: Exception) {
            emptyText.text = "Could not read messages: ${e.message}"
            emptyText.visibility = View.VISIBLE
            listView.visibility = View.GONE
            return
        }

        if (items.isEmpty()) {
            emptyText.text = "No messages yet."
            emptyText.visibility = View.VISIBLE
            listView.visibility = View.GONE
        } else {
            emptyText.visibility = View.GONE
            listView.visibility = View.VISIBLE
            listView.adapter = ArrayAdapter(this, android.R.layout.simple_list_item_1, items)
        }
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == REQUEST_READ_SMS) {
            if (grantResults.firstOrNull() == PackageManager.PERMISSION_GRANTED) {
                displayMessages()
            } else {
                findViewById<TextView>(R.id.smsEmptyText).apply {
                    text = "SMS permission denied - can't show received messages."
                    visibility = View.VISIBLE
                }
            }
        }
    }

    companion object {
        private const val REQUEST_READ_SMS = 4181
    }
}
