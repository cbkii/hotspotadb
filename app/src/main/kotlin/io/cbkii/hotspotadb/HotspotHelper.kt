package io.cbkii.hotspotadb

import android.content.Context
import android.net.wifi.WifiManager
import android.util.Log
import java.net.Inet4Address
import java.net.NetworkInterface

object HotspotHelper {
    private const val TAG = HotspotAdbModule.TAG
    private const val WIFI_AP_STATE_ENABLED = 13

    fun isHotspotActive(context: Context): Boolean =
        try {
            val wifiManager = context.getSystemService(Context.WIFI_SERVICE) as WifiManager
            val method = wifiManager.javaClass.getMethod("getWifiApState")
            val state = method.invoke(wifiManager) as Int
            val active = state == WIFI_AP_STATE_ENABLED
            Log.d(TAG, "HotspotAdb: hotspot state check method=getWifiApState state=$state expected=$WIFI_AP_STATE_ENABLED active=$active")
            active
        } catch (e: NoSuchMethodException) {
            Log.w(TAG, "HotspotAdb: hotspot state check missing getWifiApState: $e")
            false
        } catch (e: Exception) {
            Log.w(TAG, "HotspotAdb: failed to check hotspot state: $e")
            false
        }

    /**
     * Returns the IP address of the hotspot (AP) interface.
     * Filters out loopback, mobile data (rmnet*), non-wlan interfaces, and the station Wi-Fi IP.
     */
    fun getHotspotIpAddress(context: Context): String? {
        val stationIp = getStationWifiIp(context)
        return getApInterfaceIp(excludeIp = stationIp)
    }

    /** Returns any wlan/ap interface IP, optionally excluding one. */
    fun getAnyWlanIp(excludeIp: String? = null): String? = getApInterfaceIp(excludeIp)

    private fun getApInterfaceIp(excludeIp: String? = null): String? {
        try {
            val interfaces = NetworkInterface.getNetworkInterfaces() ?: return null
            val inspected = mutableListOf<String>()
            val rejected = mutableListOf<String>()
            for (iface in interfaces) {
                inspected += iface.name
                if (iface.isLoopback || !iface.isUp) {
                    rejected += "${iface.name}:loopback/down"
                    continue
                }
                // Explicit denylist for mobile-data, VPN, and CLAT tunnel interfaces.
                // We do not maintain an allowlist of AP interface name prefixes because OEMs
                // use non-standard names (e.g. "softap*", "wigig*"). Any interface that
                // survives the denylist and has an IPv4 address is a valid SoftAP candidate.
                if (
                    iface.name.startsWith("rmnet") ||
                    iface.name.startsWith("ccmni") ||
                    iface.name.startsWith("tun") ||
                    iface.name.startsWith("clat")
                ) {
                    rejected += "${iface.name}:cell/vpn/clat"
                    continue
                }
                for (addr in iface.inetAddresses) {
                    if (addr is Inet4Address && !addr.isLoopbackAddress) {
                        val ip = addr.hostAddress ?: continue
                        if (ip == excludeIp) {
                            rejected += "${iface.name}:station-ip($ip)"
                            continue
                        }
                        Log.i(TAG, "HotspotAdb: selected hotspot interface=${iface.name} ip=$ip")
                        return ip
                    }
                }
                rejected += "${iface.name}:no-ipv4"
            }
            Log.w(TAG, "HotspotAdb: no hotspot IPv4 found inspected=${inspected.joinToString()} rejected=${rejected.joinToString()}")
        } catch (e: Exception) {
            Log.w(TAG, "HotspotAdb: failed to get hotspot IP: $e")
        }
        return null
    }

    @Suppress("DEPRECATION")
    private fun getStationWifiIp(context: Context): String? {
        return try {
            val wifiManager = context.getSystemService(Context.WIFI_SERVICE) as WifiManager
            val ipInt = wifiManager.connectionInfo.ipAddress
            if (ipInt == 0) return null
            "${ipInt and 0xFF}.${ipInt shr 8 and 0xFF}.${ipInt shr 16 and 0xFF}.${ipInt shr 24 and 0xFF}"
        } catch (_: Exception) {
            null
        }
    }
}
