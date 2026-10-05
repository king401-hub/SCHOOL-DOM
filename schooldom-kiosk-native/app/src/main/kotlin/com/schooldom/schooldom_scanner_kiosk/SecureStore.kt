package com.schooldom.schooldom_scanner_kiosk

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/**
 * Hand-rolled equivalent of flutter_secure_storage's Android backend
 * (encryptedSharedPreferences: true) - androidx.security's EncryptedSharedPreferences
 * isn't usable here (not cached, no network to fetch it - see app/build.gradle.kts),
 * so this does the same thing directly: an AES-256-GCM key held in the
 * hardware-backed AndroidKeyStore (never readable outside this app, survives
 * app updates, is lost on uninstall - matching EncryptedSharedPreferences'
 * own guarantees), encrypting each value before it touches plain
 * SharedPreferences. IV is random per write and stored alongside the
 * ciphertext (GCM requires a fresh IV per encryption under the same key).
 */
object SecureStore {
    private const val PREFS_NAME = "schooldom_secure_store"
    private const val KEY_ALIAS = "schooldom_kiosk_master_key"
    private const val ANDROID_KEYSTORE = "AndroidKeyStore"
    private const val TRANSFORMATION = "AES/GCM/NoPadding"
    private const val GCM_TAG_LENGTH_BITS = 128
    private const val GCM_IV_LENGTH_BYTES = 12

    private fun prefs(context: Context) =
        context.applicationContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    private fun getOrCreateKey(): SecretKey {
        val keyStore = KeyStore.getInstance(ANDROID_KEYSTORE).apply { load(null) }
        (keyStore.getKey(KEY_ALIAS, null) as? SecretKey)?.let { return it }

        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, ANDROID_KEYSTORE)
        val spec = KeyGenParameterSpec.Builder(
            KEY_ALIAS,
            KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT,
        )
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setKeySize(256)
            .build()
        generator.init(spec)
        return generator.generateKey()
    }

    fun write(context: Context, key: String, value: String) {
        val cipher = Cipher.getInstance(TRANSFORMATION).apply {
            init(Cipher.ENCRYPT_MODE, getOrCreateKey())
        }
        val iv = cipher.iv
        val ciphertext = cipher.doFinal(value.toByteArray(Charsets.UTF_8))
        val combined = iv + ciphertext
        prefs(context).edit().putString(key, Base64.encodeToString(combined, Base64.NO_WRAP)).apply()
    }

    fun read(context: Context, key: String): String? {
        val stored = prefs(context).getString(key, null) ?: return null
        return try {
            val combined = Base64.decode(stored, Base64.NO_WRAP)
            val iv = combined.copyOfRange(0, GCM_IV_LENGTH_BYTES)
            val ciphertext = combined.copyOfRange(GCM_IV_LENGTH_BYTES, combined.size)
            val cipher = Cipher.getInstance(TRANSFORMATION).apply {
                init(Cipher.DECRYPT_MODE, getOrCreateKey(), GCMParameterSpec(GCM_TAG_LENGTH_BITS, iv))
            }
            String(cipher.doFinal(ciphertext), Charsets.UTF_8)
        } catch (e: Throwable) {
            // Corrupt entry or a key that no longer matches (e.g. keystore
            // reset) - treat exactly like "never written", same as the
            // Dart side's jsonDecode try/catch around a bad session blob.
            null
        }
    }

    fun delete(context: Context, key: String) {
        prefs(context).edit().remove(key).apply()
    }
}
