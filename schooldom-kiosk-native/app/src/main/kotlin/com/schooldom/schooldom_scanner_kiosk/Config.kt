package com.schooldom.schooldom_scanner_kiosk

/**
 * Mirrors lib/api/config.dart: this app only ever runs on real dedicated
 * terminal hardware, never an emulator, so there is no debug/emulator
 * fallback - always the production server.
 */
object Config {
    const val API_BASE_URL = "https://schooldom.academy"
}
