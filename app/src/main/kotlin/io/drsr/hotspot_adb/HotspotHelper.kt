package io.drsr.hotspot_adb

import android.content.Context
import android.net.wifi.WifiManager
import de.robv.android.xposed.XposedBridge
import java.net.Inet4Address
import java.net.NetworkInterface

object HotspotHelper {

    private const val WIFI_AP_STATE_ENABLED = 13

    fun isHotspotActive(context: Context): Boolean {
        return try {
            val wifiManager = context.getSystemService(Context.WIFI_SERVICE) as WifiManager
            val method = wifiManager.javaClass.getMethod("getWifiApState")
            val state = method.invoke(wifiManager) as Int
            state == WIFI_AP_STATE_ENABLED
        } catch (e: Exception) {
            XposedBridge.log("HotspotAdb: failed to check hotspot state: $e")
            false
        }
    }

    fun getIpAddresses(): List<String> {
        val result = mutableListOf<String>()
        try {
            val interfaces = NetworkInterface.getNetworkInterfaces() ?: return result
            for (iface in interfaces) {
                if (iface.isLoopback || !iface.isUp) continue
                for (addr in iface.inetAddresses) {
                    if (addr is Inet4Address && !addr.isLoopbackAddress) {
                        addr.hostAddress?.let { result.add(it) }
                    }
                }
            }
        } catch (e: Exception) {
            XposedBridge.log("HotspotAdb: failed to get IP addresses: $e")
        }
        return result
    }

    fun getHotspotIpAddress(): String? = getIpAddresses().firstOrNull()
}
