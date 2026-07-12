package io.drsr.hotspotadb.compat

import io.drsr.hotspotadb.ReflectionCompat
import io.github.libxposed.api.XposedModule

/** AOSP Settings class names that changed between Android 15 and Android 16. */
object SettingsAppRefs {
    const val IP_PREF_KEY = "adb_ip_addr_pref"

    private val controllerClasses =
        arrayOf(
            "com.android.settings.development.AdbWirelessDebuggingPreferenceController",
            "com.android.settings.development.WirelessDebuggingPreferenceController",
        )

    private val fragmentClasses =
        arrayOf(
            "com.android.settings.development.AdbWirelessDebuggingFragment",
            "com.android.settings.development.WirelessDebuggingFragment",
        )

    fun findControllerClass(
        classLoader: ClassLoader,
        module: XposedModule,
    ): Class<*>? =
        ReflectionCompat.findFirstClass(
            classLoader,
            module,
            "Settings Wi-Fi gate",
            *controllerClasses,
        )

    fun findWirelessDebuggingFragmentClass(
        classLoader: ClassLoader,
        module: XposedModule,
    ): Class<*>? =
        ReflectionCompat.findFirstClass(
            classLoader,
            module,
            "Settings wireless debugging fragment",
            *fragmentClasses,
        )
}
