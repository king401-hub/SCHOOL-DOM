package com.schooldom.schooldom_scanner_kiosk

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageInfo
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.BatteryManager
import android.os.Build
import android.os.Bundle
import android.os.Looper
import org.json.JSONObject
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

data class HeartbeatOutcome(
    val online: Boolean,
    val authorized: Boolean,
    val schoolName: String?,
    val pairedSchoolName: String?,
)

/**
 * Direct port of kiosk_home_screen.dart's _sendHeartbeat: reports battery,
 * charging state, app version, and (best-effort) location every few
 * minutes, and picks up remote changes (school (re)assignment, pairing,
 * revocation). NOT YET PORTED: the update_available self-update prompt -
 * tracked as a separate follow-up alongside Device Owner/kiosk-lock mode.
 *
 * Blocking - call off the main thread (matches every other network call in
 * this app's convention, see TopwisePrinterBridge/ApiClient).
 */
object Heartbeat {
    private const val TIMEOUT_MS = 10_000
    private const val LOCATION_TIMEOUT_MS = 12_000L

    fun send(context: Context, synced: Boolean): HeartbeatOutcome {
        val deviceAuthToken = KioskStore.deviceAuthToken(context)
            ?: return HeartbeatOutcome(online = false, authorized = true, schoolName = null, pairedSchoolName = null)

        val battery = batteryPercentage(context)
        val charging = isCharging(context)
        val (versionName, versionCode) = appVersion(context)
        val location = currentLocation(context)

        val payload = JSONObject().apply {
            put("auth_token", deviceAuthToken)
            put("app_version", versionName)
            if (versionCode != null) put("app_version_code", versionCode)
            if (battery >= 0) put("battery_percentage", battery)
            put("battery_charging", charging)
            put("synced", synced)
            if (location != null) {
                put("latitude", location.latitude)
                put("longitude", location.longitude)
            }
        }

        return try {
            val (status, body) = ApiClient.rawPost("/api/device-fleet/device/heartbeat/", payload, TIMEOUT_MS)
            if (status != 200) {
                return HeartbeatOutcome(online = false, authorized = true, schoolName = null, pairedSchoolName = null)
            }
            val data = if (body.isNotEmpty()) JSONObject(body) else JSONObject()
            if (!data.optBoolean("authorized", true)) {
                return HeartbeatOutcome(online = true, authorized = false, schoolName = null, pairedSchoolName = null)
            }

            val schoolId = data.optString("school_id", "")
            val schoolName = data.optString("school_name", "")
            if (schoolId.isNotEmpty() && schoolName.isNotEmpty()) {
                KioskStore.setActiveSchool(context, schoolId, schoolName)
            }

            val pairedId = if (data.has("paired_school_id") && !data.isNull("paired_school_id")) data.getString("paired_school_id") else null
            val pairedName = if (data.has("paired_school_name") && !data.isNull("paired_school_name")) data.getString("paired_school_name") else null
            KioskStore.setPairedSchool(context, pairedId, pairedName)

            HeartbeatOutcome(online = true, authorized = true, schoolName = KioskStore.schoolName(context), pairedSchoolName = pairedName)
        } catch (e: Throwable) {
            HeartbeatOutcome(online = false, authorized = true, schoolName = null, pairedSchoolName = null)
        }
    }

    private fun batteryPercentage(context: Context): Int {
        return try {
            val bm = context.getSystemService(Context.BATTERY_SERVICE) as BatteryManager
            bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
        } catch (e: Throwable) {
            -1
        }
    }

    private fun isCharging(context: Context): Boolean {
        return try {
            val intent = context.registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
            val status = intent?.getIntExtra(BatteryManager.EXTRA_STATUS, -1) ?: -1
            status == BatteryManager.BATTERY_STATUS_CHARGING || status == BatteryManager.BATTERY_STATUS_FULL
        } catch (e: Throwable) {
            false
        }
    }

    @Suppress("DEPRECATION")
    private fun legacyVersionCode(info: PackageInfo): Int = info.versionCode

    private fun appVersion(context: Context): Pair<String, Int?> {
        return try {
            val info = context.packageManager.getPackageInfo(context.packageName, 0)
            val code = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) info.longVersionCode.toInt() else legacyVersionCode(info)
            (info.versionName ?: "") to code
        } catch (e: Throwable) {
            "" to null
        }
    }

    /** Null on any failure (denied, disabled, no fix within the timeout) -
     * never guessed, same reasoning as Geolocator.getCurrentPosition on the
     * Dart side: a fixed indoor kiosk can genuinely fail to get a fix, and a
     * stale/wrong coordinate would be worse than reporting none. */
    private fun currentLocation(context: Context): Location? {
        return try {
            val lm = context.getSystemService(Context.LOCATION_SERVICE) as? LocationManager ?: return null
            val hasFine = context.checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
            val hasCoarse = context.checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED
            if (!hasFine && !hasCoarse) return null

            val provider = listOf(LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER)
                .firstOrNull { lm.isProviderEnabled(it) } ?: return null

            val latch = CountDownLatch(1)
            var result: Location? = null
            val listener = object : LocationListener {
                override fun onLocationChanged(location: Location) {
                    result = location
                    latch.countDown()
                }
                override fun onProviderEnabled(provider: String) {}
                override fun onProviderDisabled(provider: String) {}
                @Deprecated("Deprecated in Java")
                override fun onStatusChanged(provider: String?, status: Int, extras: Bundle?) {}
            }
            lm.requestSingleUpdate(provider, listener, Looper.getMainLooper())
            latch.await(LOCATION_TIMEOUT_MS, TimeUnit.MILLISECONDS)
            lm.removeUpdates(listener)
            result
        } catch (e: Throwable) {
            null
        }
    }
}
