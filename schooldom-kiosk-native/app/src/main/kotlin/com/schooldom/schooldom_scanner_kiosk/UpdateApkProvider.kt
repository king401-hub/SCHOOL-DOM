package com.schooldom.schooldom_scanner_kiosk

import android.content.ContentProvider
import android.content.ContentValues
import android.database.Cursor
import android.database.MatrixCursor
import android.net.Uri
import android.os.ParcelFileDescriptor
import android.provider.OpenableColumns
import java.io.File

/**
 * Hand-rolled equivalent of androidx.core.content.FileProvider - this app
 * deliberately has zero external dependencies (see app/build.gradle.kts),
 * so AndroidX's FileProvider isn't available. A raw file:// Uri into this
 * app's private cache dir (the previous approach, plus a StrictMode
 * exemption to stop it crashing on send) doesn't actually work either:
 * the Package Installer runs as a different app entirely and has no
 * permission to open a file in another app's private storage, regardless
 * of StrictMode or FLAG_GRANT_READ_URI_PERMISSION on a plain file:// Uri -
 * Android reports it as "No Activity found to handle Intent" because
 * nothing can resolve a URI it's not allowed to read. A ContentProvider is
 * the only way to actually hand another app bytes from here.
 *
 * Only ever serves a bare filename inside this app's own cacheDir (see
 * AppUpdater/installUpdate - the downloaded update APK), so there's no
 * path to escape it with and nothing else in the cache is exposed by name
 * guessing alone, since this provider never lists its contents.
 */
class UpdateApkProvider : ContentProvider() {
    companion object {
        const val AUTHORITY = "com.schooldom.schooldom_scanner_kiosk.updateapk"
        fun uriForFile(file: File): Uri = Uri.parse("content://$AUTHORITY/${file.name}")
    }

    override fun onCreate() = true

    override fun openFile(uri: Uri, mode: String): ParcelFileDescriptor? {
        val file = fileFor(uri) ?: return null
        return ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY)
    }

    override fun query(uri: Uri, projection: Array<out String>?, selection: String?, selectionArgs: Array<out String>?, sortOrder: String?): Cursor? {
        val file = fileFor(uri) ?: return null
        val cursor = MatrixCursor(arrayOf(OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE))
        cursor.addRow(arrayOf(file.name, file.length()))
        return cursor
    }

    override fun getType(uri: Uri) = "application/vnd.android.package-archive"
    override fun insert(uri: Uri, values: ContentValues?): Uri? = null
    override fun delete(uri: Uri, selection: String?, selectionArgs: Array<out String>?) = 0
    override fun update(uri: Uri, values: ContentValues?, selection: String?, selectionArgs: Array<out String>?) = 0

    private fun fileFor(uri: Uri): File? {
        val name = uri.lastPathSegment ?: return null
        val file = File(context?.cacheDir, File(name).name)
        return if (file.exists()) file else null
    }
}
