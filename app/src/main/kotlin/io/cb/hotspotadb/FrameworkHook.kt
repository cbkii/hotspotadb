package io.cb.hotspotadb

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.net.wifi.WifiManager
import android.util.Log
import io.github.libxposed.api.XposedModule
import java.lang.reflect.Constructor

/**
 * Hooks in system_server (android scope) that keep Wireless Debugging alive while a Wi-Fi
 * hotspot is active.
 *
 * Hook point 1 — getCurrentWifiApInfo()
 *   AdbDebuggingHandler.getCurrentWifiApInfo() returns null when no station Wi-Fi is connected,
 *   which causes the framework to refuse to start wireless debugging.  When hotspot is active we
 *   return a synthetic AdbConnectionInfo so the framework accepts the AP network.
 *
 * Hook point 2 — network monitor / receiver suppression
 *
 *   Android 16 (allowAdbWifiReconnect enabled, the default):
 *     AdbWifiNetworkMonitor is a ConnectivityManager.NetworkCallback.  Its onLost() and
 *     onCapabilitiesChanged() tear down wireless debugging when the device loses station Wi-Fi.
 *     We suppress those callbacks while hotspot is active.
 *     Candidate path on Android 16 branches: com.android.server.adb.AdbWifiNetworkMonitor.
 *
 *   Android 16 (allowAdbWifiReconnect disabled):
 *     AdbBroadcastReceiver handles WIFI_STATE_CHANGED / NETWORK_STATE_CHANGED broadcasts.
 *     Candidate path on Android 16 branches: com.android.server.adb.AdbBroadcastReceiver.
 *
 *   Android 15:
 *     Anonymous inner BroadcastReceiver classes inside AdbDebuggingHandler handle the same
 *     broadcasts.  Scanned by index and hooked identically.
 *
 *   Both AdbWifiNetworkMonitor and AdbBroadcastReceiver hooks are always installed when the
 *   classes are present, because AdbDebuggingManager chooses between them at runtime via
 *   allowAdbWifiReconnect() — we cannot predict which path will be active.
 *
 * User-initiated disables (Developer Options toggle, hotspot settings toggle) write
 * Settings.Global.ADB_WIFI_ENABLED directly and are NOT routed through AdbWifiNetworkMonitor
 * or AdbBroadcastReceiver.  Suppressing those classes does not interfere with user intent.
 *
 * AdbConnectionInfo resolution (Android 16 branch candidates):
 *   Primary: com.android.server.adb.AdbConnectionInfo (top-level, package-private ctor)
 *   Fallback: com.android.server.adb.AdbDebuggingManager$AdbConnectionInfo (Android 15 nested)
 */
object FrameworkHook {
    // Stable synthetic BSSID.  ADB uses BSSID as part of the trusted-network fingerprint.
    // Fixed value prevents trust from resetting every time hotspot is re-enabled
    // (Android randomises the real hotspot MAC on each enable cycle).
    private const val SYNTHETIC_BSSID = "02:00:00:00:00:00"

    // Resolved once at install time from the hooked getCurrentWifiApInfo() return type.
    private var connectionInfoCtor: Constructor<*>? = null

    fun install(
        classLoader: ClassLoader,
        module: XposedModule,
    ) {
        val reporter = HookReporter("system_server", module)
        hookGetCurrentWifiApInfo(classLoader, module, reporter)
        hookNetworkMonitors(classLoader, module, reporter)
        reporter.summarize()
    }

    // ---- getCurrentWifiApInfo ----

    private fun hookGetCurrentWifiApInfo(
        classLoader: ClassLoader,
        module: XposedModule,
        reporter: HookReporter,
    ) {
        val handlerClass =
            ReflectionCompat.findFirstClass(
                classLoader,
                module,
                "Framework enablement handler",
                "com.android.server.adb.AdbDebuggingManager\$AdbDebuggingHandler",
            )
        if (handlerClass == null) {
            reporter.report("Framework enablement handler", "AdbDebuggingHandler", Status.MISSING, "class not found")
            return
        }

        val method =
            ReflectionCompat.findMethod(
                handlerClass,
                module,
                "Framework enablement",
                "getCurrentWifiApInfo",
                includeInherited = true,
            )
        if (method == null) {
            reporter.report("Framework enablement", "getCurrentWifiApInfo", Status.MISSING, "method not found")
            return
        }

        module.log(Log.INFO, TAG, "HotspotAdb: getCurrentWifiApInfo returnType=${method.returnType.name}")
        connectionInfoCtor = resolveConnectionInfoCtor(classLoader, module, method.returnType, reporter)

        // Deoptimise: prevent the JIT from inlining callers (e.g. handleMessage) and
        // bypassing the hook.
        module.deoptimize(method)

        module.hook(method).intercept { chain ->
            val result = chain.proceed()
            if (result != null) {
                module.log(Log.DEBUG, TAG, "HotspotAdb: getCurrentWifiApInfo originalResult=non-null decision=pass-through")
                return@intercept result
            }
            module.log(Log.DEBUG, TAG, "HotspotAdb: getCurrentWifiApInfo originalResult=null entering synthetic branch")

            val context =
                getContext(chain.getThisObject(), module) ?: run {
                    module.log(Log.WARN, TAG, "HotspotAdb: getCurrentWifiApInfo synthetic path aborted: context extraction failed")
                    return@intercept null
                }
            if (!HotspotHelper.isHotspotActive(context)) {
                module.log(Log.DEBUG, TAG, "HotspotAdb: getCurrentWifiApInfo synthetic path aborted: hotspot inactive")
                return@intercept null
            }

            val ctor =
                connectionInfoCtor ?: run {
                    module.log(Log.WARN, TAG, "HotspotAdb: AdbConnectionInfo ctor unresolved; synthetic AP info unavailable")
                    return@intercept null
                }

            val ssid = getHotspotSsid(context)
            try {
                val info = ctor.newInstance(SYNTHETIC_BSSID, ssid)
                module.log(Log.INFO, TAG, "HotspotAdb: getCurrentWifiApInfo → synthetic (bssid=$SYNTHETIC_BSSID ssid=$ssid)")
                info
            } catch (e: ReflectiveOperationException) {
                module.log(Log.ERROR, TAG, "HotspotAdb: failed to create AdbConnectionInfo: $e")
                null
            } catch (e: IllegalArgumentException) {
                module.log(Log.ERROR, TAG, "HotspotAdb: failed to create AdbConnectionInfo: $e")
                null
            }
        }
        reporter.report("Framework enablement", "getCurrentWifiApInfo", Status.INSTALLED, "hooked successfully")
        module.log(Log.INFO, TAG, "HotspotAdb: hooked AdbDebuggingHandler.getCurrentWifiApInfo")
    }

    /**
     * Resolve AdbConnectionInfo(String bssid, String ssid) constructor.
     *
     * Android 16 branches: com.android.server.adb.AdbConnectionInfo — top-level class with
     *   package-private (String, String) constructor.
     * Android 15: com.android.server.adb.AdbDebuggingManager$AdbConnectionInfo — nested class.
     */
    private fun resolveConnectionInfoCtor(
        classLoader: ClassLoader,
        module: XposedModule,
        expectedReturnType: Class<*>,
        reporter: HookReporter,
    ): Constructor<*>? {
        ReflectionCompat.findConstructor(
            expectedReturnType,
            module,
            "AdbConnectionInfo(return-type)",
            String::class.java,
            String::class.java,
        )?.let {
            module.log(Log.INFO, TAG, "HotspotAdb: AdbConnectionInfo constructor class selected: ${it.declaringClass.name}")
            reporter.report("AdbConnectionInfo", "constructor(return-type)", Status.INSTALLED, "found in expectedReturnType")
            return it
        }
        val candidates =
            listOf(
                "com.android.server.adb.AdbConnectionInfo",
                "com.android.server.adb.AdbDebuggingManager\$AdbConnectionInfo",
            )
        for (name in candidates) {
            val clazz = ReflectionCompat.findFirstClass(classLoader, module, "AdbConnectionInfo", name) ?: continue
            if (!(expectedReturnType.isAssignableFrom(clazz) || clazz.isAssignableFrom(expectedReturnType))) {
                module.log(
                    Log.DEBUG,
                    TAG,
                    "AdbConnectionInfo candidate rejected (incompatible return type): " +
                        "candidate=${clazz.name} returnType=${expectedReturnType.name}",
                )
                continue
            }
            val ctor =
                ReflectionCompat.findConstructor(
                    clazz,
                    module,
                    "AdbConnectionInfo",
                    String::class.java,
                    String::class.java,
                )
            if (ctor != null) {
                module.log(Log.INFO, TAG, "HotspotAdb: AdbConnectionInfo constructor class selected: ${ctor.declaringClass.name}")
                reporter.report("AdbConnectionInfo", ctor.declaringClass.name, Status.INSTALLED, "found candidate ctor")
                return ctor
            }
        }
        module.log(
            Log.WARN,
            TAG,
            "AdbConnectionInfo constructor not found for returnType=${expectedReturnType.name}; synthetic AP info disabled",
        )
        reporter.report("AdbConnectionInfo", "constructor", Status.MISSING, "not found")
        return null
    }

    // ---- Network monitor / BroadcastReceiver hooks ----

    /**
     * Install all applicable network monitor hooks.
     *
     * Hooks are installed on every class that is present in the classloader.  We do not stop
     * after the first success because AdbDebuggingManager selects between AdbWifiNetworkMonitor
     * and AdbBroadcastReceiver at runtime via allowAdbWifiReconnect(); both may be compiled in.
     *
     * Hook selection order:
     *   1. AdbWifiNetworkMonitor (Android 16, NetworkCallback — NOT a BroadcastReceiver)
     *   2. AdbBroadcastReceiver  (Android 16, BroadcastReceiver)
     *   3. Anonymous inner BroadcastReceiver scan (Android 15 fallback)
     *
     * No Settings.Global.putInt fallback: that intercept is too broad and would block
     * user-initiated disables (Developer Options toggle, hotspot settings toggle).
     */
    private fun hookNetworkMonitors(
        classLoader: ClassLoader,
        module: XposedModule,
        reporter: HookReporter,
    ) {
        var anyHookInstalled = false

        // Path A: AdbWifiNetworkMonitor — ConnectivityManager.NetworkCallback (Android 16 default).
        // Not a BroadcastReceiver; hooks onLost() and onCapabilitiesChanged().
        if (hookAdbWifiNetworkMonitor(classLoader, module, reporter)) {
            anyHookInstalled = true
        }

        // Path B: AdbBroadcastReceiver — BroadcastReceiver (Android 16 when allowAdbWifiReconnect disabled).
        for (name in listOf(
            "com.android.server.adb.AdbBroadcastReceiver",
            "com.android.server.adb.AdbDebuggingManager\$AdbBroadcastReceiver",
        )) {
            val clazz = ReflectionCompat.findFirstClass(classLoader, module, "Framework teardown receiver", name) ?: continue
            if (!BroadcastReceiver::class.java.isAssignableFrom(clazz)) {
                module.log(Log.DEBUG, TAG, "HotspotAdb: $name is not a BroadcastReceiver; skipping onReceive hook")
                continue
            }
            if (hookOnReceive(clazz, module, "AdbBroadcastReceiver path ($name)", reporter)) {
                anyHookInstalled = true
            }
        }

        // Path C: anonymous inner BroadcastReceiver — Android 15 fallback.
        // Always attempt; Android 16+ may still contain nested fallback receivers.
        run {
            module.log(Log.INFO, TAG, "HotspotAdb: scanning Android 15/16 anonymous ADB BroadcastReceiver fallbacks")
            val baseName = "com.android.server.adb.AdbDebuggingManager\$AdbDebuggingHandler"
            for (i in 1..15) {
                val clazz =
                    try {
                        Class.forName("$baseName\$$i", false, classLoader)
                    } catch (e: ClassNotFoundException) {
                        // The Java compiler assigns numbers to anonymous inner classes sequentially without gaps.
                        // Encountering the first ClassNotFoundException means no further inner classes exist.
                        // Break early to avoid up to 14 expensive, unnecessary exceptions.
                        break
                    } catch (e: Throwable) {
                        module.log(Log.WARN, TAG, "HotspotAdb: unexpected error loading $baseName\$$i: $e")
                        continue
                    }
                if (!BroadcastReceiver::class.java.isAssignableFrom(clazz)) continue
                if (hookOnReceive(clazz, module, "anonymous inner class $i (Android 15)", reporter)) {
                    anyHookInstalled = true
                }
            }
        }

        if (!anyHookInstalled) {
            // No fallback to Settings.Global.putInt: that hook is too broad and blocks
            // user-driven disables.  Log the miss so it is visible in LSPosed logs.
            module.log(
                Log.WARN,
                TAG,
                "WARNING: no ADB network monitor or BroadcastReceiver hook installed; " +
                    "framework-driven wireless debugging teardown will NOT be suppressed",
            )
            reporter.report("NetworkTeardown", "all", Status.FAILED, "no suppression hooks installed")
        }
    }

    /**
     * Hook AdbWifiNetworkMonitor (ConnectivityManager.NetworkCallback) on Android 16.
     *
     * AdbDebuggingManager uses AdbWifiNetworkMonitor when allowAdbWifiReconnect() is enabled
     * (the default on Android 16).  When the station Wi-Fi network is lost or changes to a
     * state without connectivity, the monitor calls setAdbWifiState(false, reason), which
     * disables wireless debugging.
     *
     * We suppress onLost() and onCapabilitiesChanged() while hotspot is active.
     * User-initiated disables go through Settings.Global directly and are not affected.
     *
     * Android 16 branches commonly include com.android.server.adb.AdbWifiNetworkMonitor.
     */
    private fun hookAdbWifiNetworkMonitor(
        classLoader: ClassLoader,
        module: XposedModule,
        reporter: HookReporter,
    ): Boolean {
        val clazz =
            ReflectionCompat.findFirstClass(
                classLoader,
                module,
                "Framework teardown monitor",
                "com.android.server.adb.AdbWifiNetworkMonitor",
            ) ?: run {
                module.log(Log.DEBUG, TAG, "HotspotAdb: AdbWifiNetworkMonitor not found (Android < 16?)")
                reporter.report("NetworkMonitor", "AdbWifiNetworkMonitor", Status.SKIPPED, "class absent")
                return false
            }

        val networkClass =
            ReflectionCompat.findFirstClass(classLoader, module, "NetworkCallback arg", "android.net.Network") ?: run {
                module.log(Log.WARN, TAG, "HotspotAdb: android.net.Network not found; cannot hook AdbWifiNetworkMonitor")
                reporter.report("NetworkMonitor", "android.net.Network", Status.MISSING, "missing Network arg class")
                return false
            }
        val networkCapabilitiesClass =
            ReflectionCompat.findFirstClass(
                classLoader,
                module,
                "NetworkCallback arg",
                "android.net.NetworkCapabilities",
            )

        module.log(Log.INFO, TAG, "HotspotAdb: found AdbWifiNetworkMonitor; installing Android 16 NetworkCallback hooks")
        var installed = false

        var contextExtractionWarned = false

        fun createInterceptor(methodName: String): (io.github.libxposed.api.XposedInterface.Chain) -> Any? =
            { chain ->
                val ctx = getContextFromMonitor(chain.getThisObject(), module)
                if (ctx != null) {
                    if (HotspotHelper.isHotspotActive(ctx)) {
                        module.log(
                            Log.INFO,
                            TAG,
                            "HotspotAdb: blocked AdbWifiNetworkMonitor.$methodName (hotspot active)",
                        )
                        null
                    } else {
                        chain.proceed()
                    }
                } else {
                    if (!contextExtractionWarned) {
                        module.log(Log.WARN, TAG, "HotspotAdb: AdbWifiNetworkMonitor context extraction failed; pass-through")
                        contextExtractionWarned = true
                    }
                    chain.proceed()
                }
            }

        // onLost(Network): fired when the station Wi-Fi network is lost entirely.
        try {
            val onLost = clazz.getDeclaredMethod("onLost", networkClass).also { it.isAccessible = true }
            module.deoptimize(onLost)
            module.hook(onLost).intercept(createInterceptor("onLost"))
            module.log(Log.INFO, TAG, "HotspotAdb: hooked AdbWifiNetworkMonitor.onLost (${clazz.name})")
            reporter.report("NetworkMonitor", "onLost", Status.INSTALLED, "hooked successfully")
            installed = true
        } catch (t: Throwable) {
            module.log(Log.WARN, TAG, "HotspotAdb: failed to hook AdbWifiNetworkMonitor.onLost: $t")
            reporter.report("NetworkMonitor", "onLost", Status.FAILED, "exception: $t")
        }

        // onCapabilitiesChanged(Network, NetworkCapabilities): fired when network capabilities
        // change, e.g. when the Wi-Fi network loses connectivity or internet access.
        if (networkCapabilitiesClass != null) {
            try {
                val onCaps =
                    clazz
                        .getDeclaredMethod(
                            "onCapabilitiesChanged",
                            networkClass,
                            networkCapabilitiesClass,
                        ).also { it.isAccessible = true }
                module.deoptimize(onCaps)
                module.hook(onCaps).intercept(createInterceptor("onCapabilitiesChanged"))
                module.log(Log.INFO, TAG, "HotspotAdb: hooked AdbWifiNetworkMonitor.onCapabilitiesChanged (${clazz.name})")
                reporter.report("NetworkMonitor", "onCapabilitiesChanged", Status.INSTALLED, "hooked successfully")
                installed = true
            } catch (t: Throwable) {
                module.log(Log.WARN, TAG, "HotspotAdb: failed to hook AdbWifiNetworkMonitor.onCapabilitiesChanged: $t")
                reporter.report("NetworkMonitor", "onCapabilitiesChanged", Status.FAILED, "exception: $t")
            }
        } else {
            module.log(Log.WARN, TAG, "HotspotAdb: android.net.NetworkCapabilities not found; onCapabilitiesChanged hook skipped")
            reporter.report("NetworkMonitor", "onCapabilitiesChanged", Status.SKIPPED, "missing NetworkCapabilities")
        }

        return installed
    }

    private fun hookOnReceive(
        clazz: Class<*>,
        module: XposedModule,
        label: String,
        reporter: HookReporter,
    ): Boolean {
        return try {
            val onReceive =
                clazz
                    .getDeclaredMethod("onReceive", Context::class.java, Intent::class.java)
                    .also { it.isAccessible = true }

            module.hook(onReceive).intercept { chain ->
                val context = chain.getArg(0) as? Context ?: return@intercept chain.proceed()
                val intent = chain.getArg(1) as? Intent ?: return@intercept chain.proceed()
                val action = intent.action ?: return@intercept chain.proceed()

                if ((
                        action == WifiManager.WIFI_STATE_CHANGED_ACTION ||
                            action == WifiManager.NETWORK_STATE_CHANGED_ACTION
                    ) &&
                    HotspotHelper.isHotspotActive(context)
                ) {
                    module.log(Log.INFO, TAG, "HotspotAdb: suppressed broadcast $action via $label (hotspot active)")
                    null
                } else {
                    chain.proceed()
                }
            }
            module.log(Log.INFO, TAG, "HotspotAdb: hooked BroadcastReceiver.onReceive via $label")
            reporter.report("BroadcastReceiver", label, Status.INSTALLED, "hooked onReceive")
            true
        } catch (t: Throwable) {
            module.log(Log.DEBUG, TAG, "HotspotAdb: failed to hook onReceive in ${clazz.name}: $t")
            reporter.report("BroadcastReceiver", label, Status.FAILED, "exception: $t")
            false
        }
    }

    // ---- Context extraction helpers ----

    /**
     * Extract Context from an AdbDebuggingHandler instance.
     *
     * Android 15: handler is an inner class of AdbDebuggingManager.
     *   this$0 → AdbDebuggingManager → mContext
     * Android 16: handler may be top-level with a direct mContext field, or hold a reference
     *   to AdbDebuggingManager.
     */
    private fun getContext(
        handler: Any?,
        module: XposedModule,
    ): Context? {
        handler ?: return null
        return try {
            (ReflectionCompat.getFieldValueByName(handler, "mContext") as? Context)?.also {
                module.log(Log.DEBUG, TAG, "HotspotAdb: context extraction: direct handler.mContext")
                return it
            }
            val outer =
                ReflectionCompat.getFieldValueByName(handler, "this\$0")
                    ?: ReflectionCompat.getFieldValueByName(handler, "mAdbDebuggingManager")
                    ?: ReflectionCompat.getFieldValueByType(handler, "com.android.server.adb.AdbDebuggingManager")
                    ?: ReflectionCompat.getFieldByNamesOrTypes(
                        handler,
                        listOf("mManager"),
                        listOf("com.android.server.adb.AdbDebuggingManager"),
                    )?.get(handler)
            (outer?.let { ReflectionCompat.getFieldValueByName(it, "mContext") } as? Context)?.also {
                module.log(Log.DEBUG, TAG, "HotspotAdb: context extraction: manager.mContext via ${outer?.javaClass?.name}")
                return it
            }
        } catch (e: Exception) {
            module.log(Log.WARN, TAG, "HotspotAdb: failed to get context from handler: $e")
            null
        }
    }

    /**
     * Extract Context from an AdbWifiNetworkMonitor instance.
     *
     * AdbWifiNetworkMonitor holds a reference to AdbDebuggingManager (which has mContext),
     * or potentially has its own mContext field.
     */
    private fun getContextFromMonitor(
        monitor: Any?,
        module: XposedModule,
    ): Context? {
        monitor ?: return null
        return try {
            (ReflectionCompat.getFieldValueByName(monitor, "mContext") as? Context)
                ?: run {
                    val manager =
                        ReflectionCompat.getFieldValueByName(monitor, "mAdbDebuggingManager")
                            ?: ReflectionCompat.getFieldValueByType(monitor, "com.android.server.adb.AdbDebuggingManager")
                            ?: ReflectionCompat.getFieldValueByName(monitor, "this\$0")
                    manager?.let { ReflectionCompat.getFieldValueByName(it, "mContext") as? Context }
                }
        } catch (e: Exception) {
            module.log(Log.WARN, TAG, "HotspotAdb: failed to get context from AdbWifiNetworkMonitor: $e")
            null
        }
    }

    private fun getHotspotSsid(context: Context): String =
        try {
            val wm = context.getSystemService(Context.WIFI_SERVICE) as WifiManager
            val config = wm.javaClass.getMethod("getSoftApConfiguration").invoke(wm)
            val wifiSsid = config.javaClass.getMethod("getWifiSsid").invoke(config)
            wifiSsid?.toString() ?: "HotspotAP"
        } catch (_: Throwable) {
            "HotspotAP"
        }

    private const val TAG = HotspotAdbModule.TAG
}
