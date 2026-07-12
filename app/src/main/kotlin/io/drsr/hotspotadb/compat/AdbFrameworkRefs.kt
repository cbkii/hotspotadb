package io.drsr.hotspotadb.compat

import io.drsr.hotspotadb.ReflectionCompat
import io.github.libxposed.api.XposedModule

/** Android-version-specific ADB framework internals used by system_server hooks. */
object AdbFrameworkRefs {
    const val HANDLER_CLASS = "com.android.server.adb.AdbDebuggingManager\$AdbDebuggingHandler"
    const val ANONYMOUS_RECEIVER_BASE = HANDLER_CLASS
    const val ANONYMOUS_RECEIVER_SCAN_LIMIT = 15

    val connectionInfoClasses =
        listOf(
            "com.android.server.adb.AdbConnectionInfo",
            "com.android.server.adb.AdbDebuggingManager\$AdbConnectionInfo",
        )

    val networkMonitorClasses =
        listOf(
            "com.android.server.adb.AdbWifiNetworkMonitor",
            "com.android.server.adb.AdbDebuggingManager\$AdbWifiNetworkMonitor",
        )

    val broadcastReceiverClasses =
        listOf(
            "com.android.server.adb.AdbBroadcastReceiver",
            "com.android.server.adb.AdbDebuggingManager\$AdbBroadcastReceiver",
        )

    fun findHandlerClass(
        classLoader: ClassLoader,
        module: XposedModule,
    ): Class<*>? =
        ReflectionCompat.findFirstClass(
            classLoader,
            module,
            "Framework enablement handler",
            HANDLER_CLASS,
        )

    fun findNetworkMonitorClass(
        classLoader: ClassLoader,
        module: XposedModule,
    ): Class<*>? =
        ReflectionCompat.findFirstClass(
            classLoader,
            module,
            "Framework teardown monitor",
            *networkMonitorClasses.toTypedArray(),
        )
}
