package io.cb.hotspotadb.compat

import android.content.Context
import android.net.wifi.WifiManager

/** Hidden SoftAP APIs isolated from hook policy. */
object HotspotApi {
    const val WIFI_AP_STATE_ENABLED = 13
    private const val DEFAULT_SSID = "HotspotAP"

    fun getApState(context: Context): Int? {
        return try {
            val wifiManager = context.getSystemService(Context.WIFI_SERVICE) as? WifiManager ?: return null
            wifiManager.javaClass.getMethod("getWifiApState").invoke(wifiManager) as? Int
        } catch (_: ReflectiveOperationException) {
            null
        } catch (_: SecurityException) {
            null
        }
    }

    fun isApEnabled(context: Context): Boolean = getApState(context) == WIFI_AP_STATE_ENABLED

    fun getHotspotSsid(context: Context): String {
        return try {
            val wifiManager = context.getSystemService(Context.WIFI_SERVICE) as? WifiManager ?: return DEFAULT_SSID
            val config = wifiManager.javaClass.getMethod("getSoftApConfiguration").invoke(wifiManager) ?: return DEFAULT_SSID
            normalizeSsid(readWifiSsid(config) ?: readStringSsid(config)) ?: DEFAULT_SSID
        } catch (_: ReflectiveOperationException) {
            DEFAULT_SSID
        } catch (_: SecurityException) {
            DEFAULT_SSID
        }
    }

    private fun readWifiSsid(config: Any): String? =
        try {
            config.javaClass.getMethod("getWifiSsid").invoke(config)?.toString()
        } catch (_: ReflectiveOperationException) {
            null
        }

    private fun readStringSsid(config: Any): String? =
        try {
            config.javaClass.getMethod("getSsid").invoke(config) as? String
        } catch (_: ReflectiveOperationException) {
            null
        }

    private fun normalizeSsid(value: String?): String? =
        value
            ?.trim()
            ?.removeSurrounding("\"")
            ?.takeIf { it.isNotBlank() }

    @Suppress("DEPRECATION")
    fun getStationWifiIp(context: Context): String? {
        return try {
            val wifiManager = context.getSystemService(Context.WIFI_SERVICE) as? WifiManager ?: return null
            val ip = wifiManager.connectionInfo.ipAddress
            if (ip == 0) return null
            "${ip and 0xFF}.${ip shr 8 and 0xFF}.${ip shr 16 and 0xFF}.${ip shr 24 and 0xFF}"
        } catch (_: RuntimeException) {
            null
        }
    }
}
