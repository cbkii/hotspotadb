package io.drsr.hotspotadb

import android.content.Context
import android.provider.Settings
import android.util.Log
import io.drsr.hotspotadb.compat.AdbManagerCompat
import io.drsr.hotspotadb.compat.HotspotApi
import java.net.Inet4Address
import java.net.NetworkInterface

object HotspotHelper {
    const val ADB_WIFI_ENABLED = "adb_wifi_enabled"
    const val FIXED_ENDPOINT_KEY = "hotspot_adb_fixed_endpoint"
    const val FIXED_ENDPOINT_READY_KEY = "hotspot_adb_fixed_endpoint_ready"
    const val FIXED_IP = "192.168.49.1"
    const val FIXED_PORT = 5555

    private const val TAG = HotspotAdbModule.TAG

    @Volatile
    private var lastReportedState: Boolean? = null

    @Volatile
    private var lastReportedCandidate: String? = null

    fun isHotspotActive(context: Context): Boolean {
        val state = HotspotApi.getApState(context)
        val active = state == HotspotApi.WIFI_AP_STATE_ENABLED
        if (lastReportedState != active) {
            Log.i(
                TAG,
                "HotspotAdb: hotspot state changed active=$active " +
                    "state=${state ?: "unavailable"} expected=${HotspotApi.WIFI_AP_STATE_ENABLED}",
            )
            lastReportedState = active
        }
        return active
    }

    fun isAdbWifiEnabled(context: Context): Boolean = Settings.Global.getInt(context.contentResolver, ADB_WIFI_ENABLED, 0) == 1

    fun isFixedEndpointEnabled(context: Context): Boolean = Settings.Global.getInt(context.contentResolver, FIXED_ENDPOINT_KEY, 0) == 1

    fun isFixedEndpointReady(context: Context): Boolean = Settings.Global.getInt(context.contentResolver, FIXED_ENDPOINT_READY_KEY, 0) == 1

    fun setFixedEndpointReady(
        context: Context,
        ready: Boolean,
    ) {
        val old = isFixedEndpointReady(context)
        if (old != ready) {
            Settings.Global.putInt(context.contentResolver, FIXED_ENDPOINT_READY_KEY, if (ready) 1 else 0)
            Log.i(TAG, "HotspotAdb: fixed endpoint ready=$ready")
        }
    }

    fun getAdbWirelessPort(): Int = AdbManagerCompat.getWirelessPort()

    fun getHotspotSsid(context: Context): String = HotspotApi.getHotspotSsid(context)

    data class InterfaceCandidate(
        val name: String,
        val ip: String,
        val score: Int,
        val reason: String,
    )

    /** Returns the primary hotspot IPv4 address, excluding the optional fixed alias. */
    fun getHotspotIpAddress(context: Context): String? =
        findBestCandidate(
            excludeIp = HotspotApi.getStationWifiIp(context),
            allowFixedAlias = false,
        )?.ip

    /** Returns any plausible AP interface IPv4 address, optionally excluding one. */
    fun getAnyWlanIp(excludeIp: String? = null): String? =
        findBestCandidate(
            excludeIp = excludeIp,
            allowFixedAlias = false,
        )?.ip

    /** Returns the most likely SoftAP interface name for netd alias management. */
    fun getApInterfaceName(context: Context): String? =
        findBestCandidate(
            excludeIp = HotspotApi.getStationWifiIp(context),
            allowFixedAlias = true,
        )?.name

    internal fun scoreInterfaceName(name: String): Int? {
        val lower = name.lowercase()
        if (
            lower == "lo" ||
            lower.startsWith("rmnet") ||
            lower.startsWith("ccmni") ||
            lower.startsWith("tun") ||
            lower.startsWith("tap") ||
            lower.startsWith("wg") ||
            lower.startsWith("clat") ||
            lower.startsWith("v4-") ||
            lower.startsWith("dummy") ||
            lower.startsWith("ip6tnl") ||
            lower.startsWith("sit") ||
            lower.startsWith("p2p") ||
            lower.startsWith("aware") ||
            lower.startsWith("nan") ||
            lower.startsWith("bnep") ||
            lower.startsWith("bt-")
        ) {
            return null
        }
        return when {
            lower.startsWith("ap") -> 100
            lower.startsWith("swlan") -> 90
            lower.startsWith("softap") -> 80
            lower.startsWith("wlan") -> 70
            lower.startsWith("rndis") || lower.startsWith("usb") -> 10
            lower.startsWith("eth") -> 10
            else -> 50
        }
    }

    private fun findBestCandidate(
        excludeIp: String?,
        allowFixedAlias: Boolean,
    ): InterfaceCandidate? {
        val candidates = mutableListOf<InterfaceCandidate>()
        val rejected = mutableListOf<String>()
        try {
            val interfaces = NetworkInterface.getNetworkInterfaces()?.toList().orEmpty()
            for (iface in interfaces) {
                if (!iface.isUp || iface.isLoopback) {
                    rejected += "${iface.name}:down/loopback"
                    continue
                }
                val score = scoreInterfaceName(iface.name)
                if (score == null) {
                    rejected += "${iface.name}:excluded-kind"
                    continue
                }
                var acceptedAddress = false
                for (address in iface.inetAddresses) {
                    if (address !is Inet4Address || address.isLoopbackAddress || address.isLinkLocalAddress) continue
                    val ip = address.hostAddress ?: continue
                    if (ip == excludeIp) {
                        rejected += "${iface.name}:station-ip($ip)"
                        continue
                    }
                    if (!allowFixedAlias && ip == FIXED_IP) {
                        rejected += "${iface.name}:fixed-alias($ip)"
                        continue
                    }
                    candidates += InterfaceCandidate(iface.name, ip, score, "usable IPv4")
                    acceptedAddress = true
                }
                if (!acceptedAddress) rejected += "${iface.name}:no-usable-ipv4"
            }
        } catch (e: Exception) {
            Log.w(TAG, "HotspotAdb: interface enumeration failed: $e")
            return null
        }

        val selected =
            candidates
                .sortedWith(
                    compareByDescending<InterfaceCandidate> { it.score }
                        .thenBy { it.name }
                        .thenBy { it.ip == FIXED_IP }
                        .thenBy { it.ip },
                ).firstOrNull()

        val signature = selected?.let { "${it.name}/${it.ip}/${it.score}" } ?: "none"
        if (signature != lastReportedCandidate) {
            if (selected != null) {
                Log.i(
                    TAG,
                    "HotspotAdb: selected hotspot interface=${selected.name} " +
                        "ip=${selected.ip} score=${selected.score}",
                )
            } else {
                Log.w(TAG, "HotspotAdb: no hotspot IPv4 candidate; rejected=${rejected.joinToString()}")
            }
            lastReportedCandidate = signature
        }
        return selected
    }
}
