package com.schooldom.schooldom_scanner_kiosk

import android.content.Context
import android.util.Base64
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec

/**
 * Hand-rolled equivalent of flutter_secure_storage's Android backend
 * (encryptedSharedPreferences: true) - androidx.security's EncryptedSharedPreferences
 * isn't usable here (not cached, no network to fetch it - see app/build.gradle.kts),
 * so this encrypts each value before it touches plain SharedPreferences.
 *
 * The AES key is a plain software key, generated once and stored (itself
 * base64-encoded) in a separate SharedPreferences entry - NOT the
 * hardware-backed AndroidKeyStore this originally used. That traded away
 * TEE-level key isolation for something that actually works: on at least
 * one real Topwise terminal in this fleet, the very first AndroidKeyStore
 * key generation (always the first thing ProvisioningActivity does after a
 * successful activation, via SessionStore.saveSession) hung forever with no
 * exception and no timeout - confirmed live via ApiClientTrace showing the
 * server round trip itself completing in under a second, then nothing else
 * from the app at all, just the busy spinner redrawing forever. A known
 * class of bug on cheap/MediaTek Android Keystore (HAL/TEE) implementations.
 * These are session JWTs on a closed kiosk fleet, not long-term high-value
 * secrets - a permanently bricked activation screen is a far worse outcome
 * than slightly weaker at-rest protection for them.
 */
object SecureStore {
    private const val PREFS_NAME = "schooldom_secure_store"
    private const val KEY_MATERIAL_PREF = "master_key_material"
    private const val TRANSFORMATION = "AES/GCM/NoPadding"
    private const val GCM_TAG_LENGTH_BITS = 128
    private const val GCM_IV_LENGTH_BYTES = 12

    private fun prefs(context: Context) =
        context.applicationContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    @Synchronized
    private fun getOrCreateKey(context: Context): SecretKey {
        val p = prefs(context)
        val existing = p.getString(KEY_MATERIAL_PREF, null)
        if (existing != null) {
            return SecretKeySpec(Base64.decode(existing, Base64.NO_WRAP), "AES")
        }
        val generator = KeyGenerator.getInstance("AES")
        generator.init(256)
        val key = generator.generateKey()
        p.edit().putString(KEY_MATERIAL_PREF, Base64.encodeToString(key.encoded, Base64.NO_WRAP)).apply()
        return key
    }

    fun write(context: Context, key: String, value: String) {
        val cipher = Cipher.getInstance(TRANSFORMATION).apply {
            init(Cipher.ENCRYPT_MODE, getOrCreateKey(context))
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
                init(Cipher.DECRYPT_MODE, getOrCreateKey(context), GCMParameterSpec(GCM_TAG_LENGTH_BITS, iv))
            }
            String(cipher.doFinal(ciphertext), Charsets.UTF_8)
        } catch (e: Throwable) {
            // Corrupt entry or a key that no longer matches - treat exactly
            // like "never written", same as the Dart side's jsonDecode
            // try/catch around a bad session blob.
            null
        }
    }

    fun delete(context: Context, key: String) {
        prefs(context).edit().remove(key).apply()
    }
}
