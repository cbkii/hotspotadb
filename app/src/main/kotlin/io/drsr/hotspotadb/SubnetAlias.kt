package io.drsr.hotspotadb

import android.content.Context
import android.os.IBinder
import de.robv.android.xposed.XposedBridge
import java.net.Inet4Address
import java.net.NetworkInterface

/**
 * Adds FIXED_IP as a secondary address on the hotspot interface via netd.
 * Runs in system_server, which has NETWORK_STACK permission. Clients on the
 * primary hotspot subnet can reach FIXED_IP via their default gateway (the device).
 */
object SubnetAlias {
    @Volatile
    private var appliedIface: String? = null

    @Volatile
    private var frameworkLoader: ClassLoader? = null

    fun setClassLoader(loader: ClassLoader) {
        frameworkLoader = loader
    }

    @Synchronized
    fun apply(context: Context) {
        val iface = HotspotHelper.getApInterfaceName(context) ?: return
        if (appliedIface == iface && hasFixedIp(iface)) return
        if (appliedIface != null && appliedIface != iface) remove()
        val netd = getNetd() ?: return
        try {
            netd.javaClass.getMethod(
                "interfaceAddAddress",
                String::class.java,
                String::class.java,
                Int::class.javaPrimitiveType,
            ).invoke(netd, iface, HotspotHelper.FIXED_IP, 24)
            appliedIface = iface
            XposedBridge.log("HotspotAdb: aliased ${HotspotHelper.FIXED_IP}/24 on $iface")
        } catch (e: Throwable) {
            XposedBridge.log("HotspotAdb: interfaceAddAddress failed on $iface: $e")
        }
    }

    @Synchronized
    fun remove() {
        val iface = appliedIface ?: return
        appliedIface = null
        val netd = getNetd() ?: return
        try {
            netd.javaClass.getMethod(
                "interfaceDelAddress",
                String::class.java,
                String::class.java,
                Int::class.javaPrimitiveType,
            ).invoke(netd, iface, HotspotHelper.FIXED_IP, 24)
            XposedBridge.log("HotspotAdb: removed ${HotspotHelper.FIXED_IP}/24 from $iface")
        } catch (e: Throwable) {
            XposedBridge.log("HotspotAdb: interfaceDelAddress failed on $iface: $e")
        }
    }

    private fun hasFixedIp(iface: String): Boolean {
        return try {
            val ni = NetworkInterface.getByName(iface) ?: return false
            ni.inetAddresses.toList().any {
                it is Inet4Address && it.hostAddress == HotspotHelper.FIXED_IP
            }
        } catch (_: Throwable) {
            false
        }
    }

    private fun getNetd(): Any? {
        // INetd$Stub is in services.jar / APEX-repackaged connectivity jar, not on the
        // default classloader that Class.forName uses. Use the framework classloader
        // passed in via setClassLoader() (lpparam.classLoader for "android").
        val loader = frameworkLoader ?: return null
        return try {
            val sm = Class.forName("android.os.ServiceManager", true, loader)
            val binder = sm.getMethod("getService", String::class.java)
                .invoke(null, "netd") as? IBinder ?: return null
            val stub =
                try {
                    Class.forName("android.net.INetd\$Stub", true, loader)
                } catch (_: ClassNotFoundException) {
                    // APEX-repackaged name
                    Class.forName(
                        "android.net.connectivity.android.net.INetd\$Stub",
                        true,
                        loader,
                    )
                }
            stub.getMethod("asInterface", IBinder::class.java).invoke(null, binder)
        } catch (e: Throwable) {
            XposedBridge.log("HotspotAdb: getNetd failed: $e")
            null
        }
    }
}
