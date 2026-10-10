package com.schooldom.schooldom_scanner_kiosk

import android.content.Context
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import javax.net.ssl.HttpsURLConnection

/**
 * Direct port of lib/services/app_updater.dart's AppUpdater.download:
 * streams the APK straight to disk instead of buffering the whole ~50MB
 * body in memory, reporting progress as it goes. Any failure (bad status,
 * dropped connection, a body shorter than announced) throws and the
 * partial file is deleted, so a truncated APK can never reach the
 * installer. Blocking - call off the main thread.
 */
object AppUpdater {
    private const val TIMEOUT_MS = 30_000

    fun download(context: Context, url: String, destination: File, onProgress: (received: Int, total: Int?) -> Unit): File {
        try {
            val connection = URL(url).openConnection() as HttpURLConnection
            if (connection is HttpsURLConnection) {
                connection.sslSocketFactory = TlsConfig.socketFactory(context)
            }
            connection.connectTimeout = TIMEOUT_MS
            connection.readTimeout = TIMEOUT_MS
            try {
                if (connection.responseCode != 200) {
                    throw IOException("Download failed (HTTP ${connection.responseCode}).")
                }
                val total = connection.contentLength.takeIf { it >= 0 }
                var received = 0
                onProgress(0, total)

                FileOutputStream(destination).use { out ->
                    connection.inputStream.use { input ->
                        val buffer = ByteArray(16 * 1024)
                        while (true) {
                            val n = input.read(buffer)
                            if (n < 0) break
                            out.write(buffer, 0, n)
                            received += n
                            onProgress(received, total)
                        }
                    }
                }

                if (total != null && received != total) {
                    throw IOException("Download incomplete ($received of $total bytes).")
                }
                return destination
            } finally {
                connection.disconnect()
            }
        } catch (e: Throwable) {
            if (destination.exists()) destination.delete()
            throw e
        }
    }
}
