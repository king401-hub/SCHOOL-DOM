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
fun isoNow(): String {
    val format = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", Locale.US)
    format.timeZone = TimeZone.getTimeZone("UTC")
    return format.format(Date())
}
