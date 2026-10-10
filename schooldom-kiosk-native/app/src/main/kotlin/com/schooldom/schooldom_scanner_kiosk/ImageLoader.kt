package com.schooldom.schooldom_scanner_kiosk

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import java.net.HttpURLConnection
import java.net.URL
import javax.net.ssl.HttpsURLConnection

/**
 * Minimal image fetch-and-decode, no caching - there is no Maven access on
 * this machine to pull in a real image-loading library (see
 * app/build.gradle.kts), and the result screen only ever needs one photo at
 * a time, shown for a few seconds. Reuses TlsConfig's socket factory like
 * every other HTTPS call this app makes, since this old Android device
 * needs it for schooldom.academy the same way ApiClient does.
 *
 * Blocking - call off the main thread.
 */
object ImageLoader {
    private const val TIMEOUT_MS = 8_000

    fun fetch(context: Context, url: String): Bitmap? {
        return try {
            val connection = URL(url).openConnection() as HttpURLConnection
            if (connection is HttpsURLConnection) {
                connection.sslSocketFactory = TlsConfig.socketFactory(context)
            }
            connection.connectTimeout = TIMEOUT_MS
            connection.readTimeout = TIMEOUT_MS
            try {
                if (connection.responseCode != HttpURLConnection.HTTP_OK) return null
                connection.inputStream.use { BitmapFactory.decodeStream(it) }
            } finally {
                connection.disconnect()
            }
        } catch (e: Throwable) {
            null
        }
    }
}
