package io.cb.hotspotadb.compat

import android.os.IBinder
import android.util.Log
import io.cb.hotspotadb.HotspotAdbModule
import io.github.libxposed.api.XposedModule

/** Reflective INetd access across legacy and Connectivity-mainline class names. */
object NetdCompat {
    private val stubClassNames =
        arrayOf(
            "android.net.INetd\$Stub",
            "com.android.connectivity.android.net.INetd\$Stub",
            "android.net.connectivity.android.net.INetd\$Stub",
        )

    fun getNetd(
        classLoader: ClassLoader,
        module: XposedModule,
    ): Any? {
        return try {
            val serviceManager = Class.forName("android.os.ServiceManager", true, classLoader)
            val binder =
                serviceManager
                    .getMethod("getService", String::class.java)
                    .invoke(null, "netd") as? IBinder ?: return null
            val stub =
                stubClassNames.firstNotNullOfOrNull { name ->
                    try {
                        Class.forName(name, false, classLoader)
                    } catch (_: ClassNotFoundException) {
                        null
                    }
                } ?: run {
                    module.log(Log.WARN, HotspotAdbModule.TAG, "HotspotAdb: INetd Stub class not found")
                    return null
                }
            stub.getMethod("asInterface", IBinder::class.java).invoke(null, binder)
        } catch (e: ReflectiveOperationException) {
            module.log(Log.WARN, HotspotAdbModule.TAG, "HotspotAdb: netd lookup failed: $e")
            null
        } catch (e: SecurityException) {
            module.log(Log.WARN, HotspotAdbModule.TAG, "HotspotAdb: netd lookup denied: $e")
            null
        }
    }

    fun addAddress(
        netd: Any,
        iface: String,
        address: String,
        prefixLength: Int,
    ) {
        netd.javaClass
            .getMethod(
                "interfaceAddAddress",
                String::class.java,
                String::class.java,
                Int::class.javaPrimitiveType,
            ).invoke(netd, iface, address, prefixLength)
    }

    fun removeAddress(
        netd: Any,
        iface: String,
        address: String,
        prefixLength: Int,
    ) {
        netd.javaClass
            .getMethod(
                "interfaceDelAddress",
                String::class.java,
                String::class.java,
                Int::class.javaPrimitiveType,
            ).invoke(netd, iface, address, prefixLength)
    }
}
