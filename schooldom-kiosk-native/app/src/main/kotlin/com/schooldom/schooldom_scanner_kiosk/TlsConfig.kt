package com.schooldom.schooldom_scanner_kiosk

import android.content.Context
import java.net.InetAddress
import java.net.Socket
import java.security.KeyStore
import java.security.cert.CertificateFactory
import javax.net.ssl.SSLContext
import javax.net.ssl.SSLSocket
import javax.net.ssl.SSLSocketFactory
import javax.net.ssl.TrustManagerFactory

/**
 * Works around a real, confirmed failure on the fleet's oldest terminals
 * (Android 7.0 / API 24, firmware frozen since manufacture - no OS updates
 * were ever coming), diagnosed live against the real terminal in two parts:
 *
 * 1. Cloudflare's edge certificate for schooldom.academy turned out to be
 *    ECDSA-only (issued via Google Trust Services), with no RSA cipher path
 *    at all - confirmed directly with openssl (forcing an RSA-only TLS 1.2
 *    ClientHello got the exact same handshake failure the device did).
 *    This vendor's ~2016 BoringSSL/Conscrypt build cannot reliably complete
 *    an ECDHE-ECDSA handshake (fails with UNKNOWN_CIPHER_RETURNED even
 *    though its own Java API claims to support the suite), and there was no
 *    RSA fallback to use instead. Fixed at the infrastructure level, not in
 *    this app: the DNS record for schooldom.academy was switched from
 *    Cloudflare-proxied to DNS-only, and the origin's own Let's Encrypt
 *    certificate was re-issued as RSA (it was ECDSA too) - the device now
 *    talks directly to the origin's RSA cert, bypassing Cloudflare's edge
 *    entirely.
 * 2. Even with an RSA cert available, the device's bundled "com.android.
 *    okhttp" tries TLS 1.3 first (unsupported - TLS 1.3 only landed in
 *    Android API 29) and its automatic downgrade-retry trips Cloudflare's
 *    (and possibly the origin's) anti-fallback protection. Restricting the
 *    client to TLS 1.2 only, with a conservative/long-established cipher
 *    list, avoids that retry path entirely.
 *
 * The bundled-certificate TrustManager below is kept as defense in depth:
 * harmless, and reasonable since this app only ever talks to one host (see
 * Config.API_BASE_URL) - trusting only this chain is strictly narrower than
 * the full system CA list, not a compromise. Bundles the origin's actual
 * chain (Let's Encrypt's newer short-lived hierarchy: leaf -> YR1 -> an
 * intermediate root -> ISRG Root X1), re-exported after the Cloudflare
 * bypass above changed which chain the device actually sees.
 */
object TlsConfig {
    @Volatile private var cachedFactory: SSLSocketFactory? = null

    fun socketFactory(context: Context): SSLSocketFactory {
        cachedFactory?.let { return it }
        synchronized(this) {
            cachedFactory?.let { return it }
            val factory = Tls12OnlySocketFactory(build(context))
            cachedFactory = factory
            return factory
        }
    }

    private fun build(context: Context): SSLSocketFactory {
        val certFactory = CertificateFactory.getInstance("X.509")
        val keyStore = KeyStore.getInstance(KeyStore.getDefaultType())
        keyStore.load(null, null)

        for ((alias, rawResId) in listOf(
            "schooldom_intermediate" to R.raw.intermediate_le_yr1,
            "schooldom_intermediate_root" to R.raw.intermediate_root_yr,
            "schooldom_root" to R.raw.root_isrg_x1,
        )) {
            context.resources.openRawResource(rawResId).use { stream ->
                val cert = certFactory.generateCertificate(stream)
                keyStore.setCertificateEntry(alias, cert)
            }
        }

        val trustManagerFactory = TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm())
        trustManagerFactory.init(keyStore)

        val sslContext = SSLContext.getInstance("TLS")
        sslContext.init(null, trustManagerFactory.trustManagers, null)
        return sslContext.socketFactory
    }
}

/** Delegates every socket-creation overload to [delegate], then restricts
 * the returned socket to TLS 1.2 and a conservative, long-established
 * cipher suite list before it's used. Restricting the protocol alone
 * (confirmed live, this device) was NOT enough - the handshake still failed
 * with UNKNOWN_CIPHER_RETURNED even under TLS 1.2, meaning this vendor's
 * BoringSSL build advertises (getSupportedCipherSuites) at least one cipher
 * its own native handshake code doesn't actually implement correctly: the
 * server reasonably picks a cipher the client claimed to support, and the
 * native layer then can't process its own server's response. Only offering
 * ciphers universally implemented since ~2014 (long before this device's
 * 2016-era firmware) avoids relying on whatever this specific MediaTek
 * BoringSSL fork's cipher list claims versus what it actually implements. */
private class Tls12OnlySocketFactory(private val delegate: SSLSocketFactory) : SSLSocketFactory() {
    private val safeCipherSuites = listOf(
        "TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256",
        "TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384",
        "TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA",
        "TLS_ECDHE_RSA_WITH_AES_256_CBC_SHA",
        "TLS_RSA_WITH_AES_128_GCM_SHA256",
        "TLS_RSA_WITH_AES_128_CBC_SHA",
        "TLS_RSA_WITH_AES_256_CBC_SHA",
    )

    private fun restrict(socket: Socket): Socket {
        if (socket is SSLSocket) {
            socket.enabledProtocols = arrayOf("TLSv1.2")
            val offered = socket.supportedCipherSuites.toSet()
            val toEnable = safeCipherSuites.filter { it in offered }
            if (toEnable.isNotEmpty()) {
                socket.enabledCipherSuites = toEnable.toTypedArray()
            }
        }
        return socket
    }

    override fun getDefaultCipherSuites(): Array<String> = delegate.defaultCipherSuites
    override fun getSupportedCipherSuites(): Array<String> = delegate.supportedCipherSuites

    override fun createSocket(s: Socket, host: String, port: Int, autoClose: Boolean): Socket =
        restrict(delegate.createSocket(s, host, port, autoClose))

    override fun createSocket(host: String, port: Int): Socket =
        restrict(delegate.createSocket(host, port))

    override fun createSocket(host: String, port: Int, localHost: InetAddress, localPort: Int): Socket =
        restrict(delegate.createSocket(host, port, localHost, localPort))

    override fun createSocket(host: InetAddress, port: Int): Socket =
        restrict(delegate.createSocket(host, port))

    override fun createSocket(address: InetAddress, port: Int, localAddress: InetAddress, localPort: Int): Socket =
        restrict(delegate.createSocket(address, port, localAddress, localPort))
}
