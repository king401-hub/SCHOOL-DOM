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

    // The result screen only ever shows this at 110dp (see activity_home.xml's
    // resultPhoto) - profile_picture uploads are never resized server-side
    // (users.models.User has no save() override for it), so a photo
    // straight off a phone camera decodes at full resolution (easily
    // 3000x4000px) into tens of MB of raw ARGB_8888 pixels. Confirmed live:
    // a photo that rendered fine in a browser never appeared on the kiosk at
    // all - decodeStream's OutOfMemoryError on this fleet's low-RAM
    // terminals was silently swallowed by the catch below. Downsampling
    // before the real decode keeps the allocation proportional to what's
    // actually drawn.
    private const val TARGET_SIZE_PX = 300

    fun fetch(context: Context, url: String): Bitmap? {
        return try {
            val connection = URL(url).openConnection() as HttpURLConnection
            if (connection is HttpsURLConnection) {
                connection.sslSocketFactory = TlsConfig.socketFactory(context)
            }
            connection.connectTimeout = TIMEOUT_MS
            connection.readTimeout = TIMEOUT_MS
            val bytes = try {
                if (connection.responseCode != HttpURLConnection.HTTP_OK) return null
                connection.inputStream.use { it.readBytes() }
            } finally {
                connection.disconnect()
            }
            decodeSampled(bytes)
        } catch (e: Throwable) {
            null
        }
    }

    private fun decodeSampled(bytes: ByteArray): Bitmap? {
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
        if (bounds.outWidth <= 0 || bounds.outHeight <= 0) return null

        var sampleSize = 1
        while (bounds.outWidth / (sampleSize * 2) >= TARGET_SIZE_PX &&
            bounds.outHeight / (sampleSize * 2) >= TARGET_SIZE_PX
        ) {
            sampleSize *= 2
        }
        val opts = BitmapFactory.Options().apply { inSampleSize = sampleSize }
        return try {
            BitmapFactory.decodeByteArray(bytes, 0, bytes.size, opts)
        } catch (e: Throwable) {
            null
        }
    }
}
