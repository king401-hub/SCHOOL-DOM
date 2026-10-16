package com.schooldom.schooldom_scanner_kiosk

import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

/** ISO-8601 UTC timestamp, matching Dart's DateTime.now().toIso8601String()
 * closely enough for these fields (queuedAt / signedInAt - read by nothing
 * but this app itself). java.time is API 26+ and minSdk here is 24 (the
 * real fleet's oldest confirmed terminal), with no desugaring library
 * available offline to back-port it - SimpleDateFormat has worked since
 * API 1. */
fun isoNow(): String = isoAt(System.currentTimeMillis())

/** Same format as isoNow(), for a specific moment rather than "now" - used
 * to stamp a scan with the real time it happened (ScanHandler captures this
 * at the moment of the tap), not whenever the request actually gets sent.
 * That distinction matters once a scan queues offline and replays later:
 * without it, the server would date/time-stamp the attendance (and the
 * parent SMS) at replay time instead of the real tap time. */
fun isoAt(epochMillis: Long): String {
    val format = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", Locale.US)
    format.timeZone = TimeZone.getTimeZone("UTC")
    return format.format(Date(epochMillis))
}
