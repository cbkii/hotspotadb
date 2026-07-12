package io.drsr.hotspotadb

import android.content.Context
import android.util.Log
import io.drsr.hotspotadb.compat.NetdCompat
import io.github.libxposed.api.XposedModule
import java.net.Inet4Address
import java.net.NetworkInterface

/** Manages the optional fixed /32 address on the active SoftAP interface. */
object SubnetAlias {
    private const val PREFIX_LENGTH = 32

    @Volatile
    private var appliedInterface: String? = null

    @Volatile
    private var addressOwnedByModule = false

    @Synchronized
    fun apply(
        context: Context,
        classLoader: ClassLoader,
        module: XposedModule,
    ): Boolean {
        val iface = HotspotHelper.getApInterfaceName(context) ?: run {
            module.log(Log.WARN, HotspotAdbModule.TAG, "HotspotAdb: fixed alias skipped; AP interface unavailable")
            return false
        }

        val existingInterface = findInterfaceWithFixedAddress()
        if (existingInterface != null) {
            if (existingInterface != iface) {
                module.log(
                    Log.ERROR,
                    HotspotAdbModule.TAG,
                    "HotspotAdb: fixed IP ${HotspotHelper.FIXED_IP} already belongs to $existingInterface; refusing alias on $iface",
                )
                return false
            }
            appliedInterface = iface
            addressOwnedByModule = false
            return true
        }

        if (appliedInterface != null && appliedInterface != iface) {
            remove(classLoader, module)
        }

        val netd = NetdCompat.getNetd(classLoader, module) ?: return false
        return try {
            NetdCompat.addAddress(netd, iface, HotspotHelper.FIXED_IP, PREFIX_LENGTH)
            appliedInterface = iface
            addressOwnedByModule = true
            module.log(
                Log.INFO,
                HotspotAdbModule.TAG,
                "HotspotAdb: added ${HotspotHelper.FIXED_IP}/$PREFIX_LENGTH to $iface",
            )
            true
        } catch (e: ReflectiveOperationException) {
            module.log(Log.ERROR, HotspotAdbModule.TAG, "HotspotAdb: netd add-address failed on $iface: $e")
            false
        } catch (e: SecurityException) {
            module.log(Log.ERROR, HotspotAdbModule.TAG, "HotspotAdb: netd add-address denied on $iface: $e")
            false
        }
    }

    @Synchronized
    fun remove(
        classLoader: ClassLoader,
        module: XposedModule,
    ) {
        val iface = appliedInterface ?: return
        val owned = addressOwnedByModule
        appliedInterface = null
        addressOwnedByModule = false
        if (!owned) return

        val netd = NetdCompat.getNetd(classLoader, module) ?: return
        try {
            NetdCompat.removeAddress(netd, iface, HotspotHelper.FIXED_IP, PREFIX_LENGTH)
            module.log(
                Log.INFO,
                HotspotAdbModule.TAG,
                "HotspotAdb: removed ${HotspotHelper.FIXED_IP}/$PREFIX_LENGTH from $iface",
            )
        } catch (e: ReflectiveOperationException) {
            module.log(Log.WARN, HotspotAdbModule.TAG, "HotspotAdb: netd remove-address failed on $iface: $e")
        } catch (e: SecurityException) {
            module.log(Log.WARN, HotspotAdbModule.TAG, "HotspotAdb: netd remove-address denied on $iface: $e")
        }
    }

    private fun findInterfaceWithFixedAddress(): String? =
        try {
            NetworkInterface.getNetworkInterfaces()?.toList().orEmpty().firstNotNullOfOrNull { iface ->
                val containsAddress =
                    iface.inetAddresses.toList().any { address ->
                        address is Inet4Address && address.hostAddress == HotspotHelper.FIXED_IP
                    }
                iface.name.takeIf { containsAddress }
            }
        } catch (_: Exception) {
            null
        }
}
