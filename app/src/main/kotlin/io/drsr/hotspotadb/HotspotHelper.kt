package io.drsr.hotspotadb

import android.content.Context
import android.net.wifi.WifiManager
import android.util.Log
import java.net.Inet4Address
import java.net.NetworkInterface

object HotspotHelper {
    private const val TAG = HotspotAdbModule.TAG

    /**
     * Hidden Android constant for WifiManager.WIFI_AP_STATE_ENABLED.
     * Reflection is used because this is not in the public SDK but is stable across AOSP branches.
     */
    private const val WIFI_AP_STATE_ENABLED = 13
    private var lastReportedState: Boolean? = null

    fun isHotspotActive(context: Context): Boolean {
        return try {
            val wifiManager = context.getSystemService(Context.WIFI_SERVICE) as? WifiManager
            if (wifiManager == null) {
                if (lastReportedState != false) {
                    Log.w(TAG, "HotspotAdb: WIFI_SERVICE not found or wrong type")
                    lastReportedState = false
                }
                return false
            }
            val method = wifiManager.javaClass.getMethod("getWifiApState")
            val state = method.invoke(wifiManager) as Int
            val active = state == WIFI_AP_STATE_ENABLED
            if (lastReportedState != active) {
                Log.i(
                    TAG,
                    "HotspotAdb: hotspot state changed to active=$active (state=$state expected=$WIFI_AP_STATE_ENABLED)",
                )
                lastReportedState = active
            }
            active
        } catch (e: Exception) {
            if (lastReportedState != false) {
                Log.w(TAG, "HotspotAdb: failed to check hotspot state: $e")
                lastReportedState = false
            }
            false
        }
    }

    data class InterfaceCandidate(
        val name: String,
        val ip: String,
        val score: Int,
        val reason: String,
    )

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
            val interfaces = NetworkInterface.getNetworkInterfaces()?.toList() ?: return null
            val candidates = mutableListOf<InterfaceCandidate>()
            val rejected = mutableListOf<String>()

            for (iface in interfaces) {
                if (iface.isLoopback || !iface.isUp) {
                    rejected.add("${iface.name}:loopback/down")
                    continue
                }

                if (
                    iface.name.startsWith("rmnet") ||
                    iface.name.startsWith("ccmni") ||
                    iface.name.startsWith("tun") ||
                    iface.name.startsWith("clat")
                ) {
                    rejected.add("${iface.name}:cell/vpn/clat")
                    continue
                }

                for (addr in iface.inetAddresses) {
                    if (addr is Inet4Address && !addr.isLoopbackAddress) {
                        val ip = addr.hostAddress ?: continue
                        if (ip == excludeIp) {
                            rejected.add("${iface.name}:station-ip($ip)")
                            continue
                        }

                        val score =
                            when {
                                iface.name.startsWith("ap") -> 100
                                iface.name.startsWith("swlan") -> 90
                                iface.name.startsWith("softap") -> 80
                                iface.name.startsWith("wlan") -> 70
                                iface.name.startsWith("rndis") -> 10 // USB tethering fallback
                                iface.name.startsWith("eth") -> 10 // Ethernet fallback
                                else -> 50
                            }

                        candidates.add(InterfaceCandidate(iface.name, ip, score, "valid IPv4"))
                        break
                    }
                }
                if (candidates.none { it.name == iface.name }) {
                    rejected.add("${iface.name}:no-ipv4")
                }
            }

            val bestCandidate =
                candidates
                    .sortedWith(compareByDescending<InterfaceCandidate> { it.score }.thenBy { it.name }.thenBy { it.ip })
                    .firstOrNull()

            if (bestCandidate != null) {
                Log.i(
                    TAG,
                    "HotspotAdb: selected hotspot interface=${bestCandidate.name} ip=${bestCandidate.ip} score=${bestCandidate.score}",
                )
                return bestCandidate.ip
            } else {
                Log.w(
                    TAG,
                    "HotspotAdb: no hotspot IPv4 found. rejected=${rejected.joinToString()}",
                )
            }
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
