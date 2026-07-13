package io.drsr.hotspotadb

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.database.ContentObserver
import android.net.Uri
import android.net.wifi.WifiManager
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.util.Log
import io.github.libxposed.api.XposedModule
import java.lang.reflect.Method
import java.util.Collections
import java.util.WeakHashMap

/**
 * Hooks inside the com.android.settings process.
 *
 * Three hooks:
 *
 * 1. WirelessDebuggingPreferenceController.isWifiConnected(Context)
 *    Returns true when hotspot is active so the Wireless Debugging UI stays usable.
 *
 * 2. AdbIpAddressPreferenceController.getIpv4Address()
 *    Returns the hotspot AP interface IP instead of the station Wi-Fi IP when hotspot is active.
 *
 * 3. WifiTetherSettings.onStart() / onStop()
 *    onStart injects a "Wireless debugging" toggle and registers state listeners.
 *    onStop unregisters listeners and cancels pending handler callbacks.
 *
 * All hook symbols remain explicit. Shared reflection code only handles class lookup, field access,
 * and deterministic overload compatibility because modern libxposed does not provide XposedHelpers.
 */
object SettingsHook {
    private const val ADB_WIFI_ENABLED = "adb_wifi_enabled"
    private const val WIFI_AP_STATE_CHANGED_ACTION = "android.net.wifi.WIFI_AP_STATE_CHANGED"
    private const val METHOD_CACHE_MAX_SIZE = 256

    private val fragmentExtras: MutableMap<Any, MutableMap<String, Any?>> =
        Collections.synchronizedMap(WeakHashMap())

    private val methodCache: MutableMap<String, Method> =
        Collections.synchronizedMap(
            object : java.util.LinkedHashMap<String, Method>(METHOD_CACHE_MAX_SIZE, 0.75f, true) {
                override fun removeEldestEntry(eldest: MutableMap.MutableEntry<String, Method>?): Boolean = size > METHOD_CACHE_MAX_SIZE
            },
        )

    fun install(
        classLoader: ClassLoader,
        module: XposedModule,
    ) {
        val reporter = HookReporter("com.android.settings", module)
        hookIsWifiConnected(classLoader, module, reporter)
        hookGetIpv4Address(classLoader, module, reporter)
        hookWifiTetherSettings(classLoader, module, reporter)
        reporter.summarize()
    }

    private fun hookIsWifiConnected(
        classLoader: ClassLoader,
        module: XposedModule,
        reporter: HookReporter,
    ) {
        val clazz =
            ReflectionCompat.findFirstClass(
                classLoader,
                module,
                "Settings Wi-Fi gate",
                "com.android.settings.development.AdbWirelessDebuggingPreferenceController",
                "com.android.settings.development.WirelessDebuggingPreferenceController",
            )
        if (clazz == null) {
            reporter.report("Settings Wi-Fi gate", "Controller", Status.MISSING, "class not found")
            return
        }
        val method =
            ReflectionCompat.findMethod(
                clazz,
                module,
                "Settings Wi-Fi gate",
                "isWifiConnected",
                includeInherited = true,
                Context::class.java,
            )
        if (method == null) {
            reporter.report("Settings Wi-Fi gate", "isWifiConnected", Status.MISSING, "method not found")
            return
        }

        module.hook(method).intercept { chain ->
            val result = chain.proceed()
            if (result == false) {
                val context = chain.getArg(0) as? Context ?: return@intercept result
                val hotspotActive = HotspotHelper.isHotspotActive(context)
                module.log(
                    Log.INFO,
                    TAG,
                    "HotspotAdb: isWifiConnected original=$result hotspotActive=$hotspotActive",
                )
                if (hotspotActive) {
                    module.log(Log.INFO, TAG, "HotspotAdb: isWifiConnected decision=changed(true)")
                    true
                } else {
                    module.log(Log.INFO, TAG, "HotspotAdb: isWifiConnected decision=pass-through(false)")
                    result
                }
            } else {
                module.log(Log.INFO, TAG, "HotspotAdb: isWifiConnected original=$result decision=pass-through")
                result
            }
        }
        reporter.report(
            "Settings Wi-Fi gate",
            "isWifiConnected",
            Status.INSTALLED,
            "hooked ${clazz.simpleName}",
        )
        module.log(Log.INFO, TAG, "HotspotAdb: hooked ${clazz.simpleName}.isWifiConnected")
    }

    private fun hookGetIpv4Address(
        classLoader: ClassLoader,
        module: XposedModule,
        reporter: HookReporter,
    ) {
        val clazz =
            ReflectionCompat.findFirstClass(
                classLoader,
                module,
                "Settings IPv4",
                "com.android.settings.development.AdbIpAddressPreferenceController",
            )
        if (clazz == null) {
            reporter.report("Settings IPv4", "Controller", Status.MISSING, "class not found")
            return
        }
        val method =
            ReflectionCompat.findMethod(
                clazz,
                module,
                "Settings IPv4",
                "getIpv4Address",
                includeInherited = true,
            )
        if (method == null) {
            reporter.report("Settings IPv4", "getIpv4Address", Status.MISSING, "method not found")
            return
        }

        module.hook(method).intercept { chain ->
            val thisObj = chain.getThisObject() ?: return@intercept chain.proceed()
            val context =
                ReflectionCompat.getFieldValueByName(thisObj, "mContext") as? Context
                    ?: return@intercept chain.proceed()
            if (!HotspotHelper.isHotspotActive(context)) return@intercept chain.proceed()
            val ip = HotspotHelper.getHotspotIpAddress(context) ?: return@intercept chain.proceed()
            module.log(Log.INFO, TAG, "HotspotAdb: getIpv4Address → $ip (hotspot AP interface)")
            ip
        }
        reporter.report("Settings IPv4", "getIpv4Address", Status.INSTALLED, "hooked")
        module.log(Log.INFO, TAG, "HotspotAdb: hooked AdbIpAddressPreferenceController.getIpv4Address")
    }

    private fun hookWifiTetherSettings(
        classLoader: ClassLoader,
        module: XposedModule,
        reporter: HookReporter,
    ) {
        val clazz =
            ReflectionCompat.findFirstClass(
                classLoader,
                module,
                "Settings tether fragment",
                "com.android.settings.wifi.tether.WifiTetherSettings",
            )
        if (clazz == null) {
            reporter.report("Settings tether fragment", "WifiTetherSettings", Status.MISSING, "class not found")
            return
        }

        val onStart =
            ReflectionCompat.findMethod(
                clazz,
                module,
                "Settings tether fragment",
                "onStart",
                includeInherited = true,
            )
        val onStop =
            ReflectionCompat.findMethod(
                clazz,
                module,
                "Settings tether fragment",
                "onStop",
                includeInherited = true,
            )
        if (onStart == null || onStop == null) {
            reporter.report("Settings tether fragment", "onStart/onStop", Status.MISSING, "lifecycle methods missing")
            return
        }

        module.hook(onStart).intercept { chain ->
            chain.proceed()
            try {
                injectWirelessDebuggingPref(chain.getThisObject()!!, classLoader, module)
            } catch (e: Throwable) {
                module.log(Log.ERROR, TAG, "HotspotAdb: failed to inject wireless debugging preference: $e")
            }
            null
        }
        module.log(Log.INFO, TAG, "HotspotAdb: hooked WifiTetherSettings.onStart")

        module.hook(onStop).intercept { chain ->
            try {
                cleanupFragment(chain.getThisObject()!!, module)
            } catch (e: Throwable) {
                module.log(Log.ERROR, TAG, "HotspotAdb: fragment cleanup failed: $e")
            }
            chain.proceed()
            null
        }
        reporter.report("Settings tether fragment", "onStart/onStop", Status.INSTALLED, "hooked successfully")
        module.log(Log.INFO, TAG, "HotspotAdb: hooked WifiTetherSettings.onStop for listener cleanup")
    }

    private fun injectWirelessDebuggingPref(
        fragment: Any,
        classLoader: ClassLoader,
        module: XposedModule,
    ) {
        val screen =
            callMethod(fragment, "getPreferenceScreen") ?: run {
                module.log(Log.WARN, TAG, "HotspotAdb: getPreferenceScreen returned null")
                return
            }
        val context =
            callMethod(screen, "getContext") as? Context ?: run {
                module.log(Log.WARN, TAG, "HotspotAdb: could not get Context from PreferenceScreen")
                return
            }

        val existingPref = callMethod(screen, "findPreference", "hotspot_adb_wireless_debugging")
        val pref: Any = existingPref ?: createAndAddPreference(screen, context, classLoader, module) ?: return
        registerListenersIfNeeded(fragment, context, pref, module)
    }

    private fun createAndAddPreference(
        screen: Any,
        context: Context,
        classLoader: ClassLoader,
        module: XposedModule,
    ): Any? {
        val prefClass =
            ReflectionCompat.tryFindClass("com.android.settingslib.PrimarySwitchPreference", classLoader)
                ?: ReflectionCompat.tryFindClass("androidx.preference.SwitchPreferenceCompat", classLoader)
                ?: run {
                    module.log(Log.WARN, TAG, "HotspotAdb: no usable Preference subclass found; toggle injection skipped")
                    return null
                }
        val pref = prefClass.getConstructor(Context::class.java).newInstance(context)

        callMethod(pref, "setKey", "hotspot_adb_wireless_debugging")
        callMethod(pref, "setTitle", "Wireless debugging" as CharSequence)
        // Show the effective state: wireless debugging is usable only when both ADB Wi-Fi and
        // hotspot are active. Mirrors upstream's updatePrefState logic (commit 5b6437a).
        val enabled = isAdbWifiEnabled(context) && HotspotHelper.isHotspotActive(context)
        callMethod(pref, "setChecked", enabled)
        callMethod(pref, "setSummary", getWirelessDebuggingSummary(context, enabled) as CharSequence)

        val changeListenerClass =
            ReflectionCompat.tryFindClass(
                "androidx.preference.Preference\$OnPreferenceChangeListener",
                classLoader,
            ) ?: run {
                module.log(Log.WARN, TAG, "HotspotAdb: OnPreferenceChangeListener class not found; toggle will not respond")
                return null
            }
        val changeProxy =
            java.lang.reflect.Proxy.newProxyInstance(
                classLoader,
                arrayOf(changeListenerClass),
            ) { _, _, args ->
                val newValue = args!![1] as Boolean
                module.log(Log.INFO, TAG, "HotspotAdb: user toggled wireless debugging via hotspot screen: $newValue")
                Settings.Global.putInt(context.contentResolver, ADB_WIFI_ENABLED, if (newValue) 1 else 0)
                callMethod(pref, "setSummary", getWirelessDebuggingSummary(context, newValue) as CharSequence)
                true
            }
        callMethod(pref, "setOnPreferenceChangeListener", changeProxy)

        val clickListenerClass =
            ReflectionCompat.tryFindClass(
                "androidx.preference.Preference\$OnPreferenceClickListener",
                classLoader,
            )
        if (clickListenerClass != null) {
            val clickProxy =
                java.lang.reflect.Proxy.newProxyInstance(
                    classLoader,
                    arrayOf(clickListenerClass),
                ) { _, _, _ ->
                    try {
                        val subSettingsClass =
                            ReflectionCompat.tryFindClass("com.android.settings.SubSettings", context.classLoader)
                                ?: ReflectionCompat.tryFindClass("com.android.settings.SubSettings", classLoader)
                        if (subSettingsClass != null) {
                            val fragmentClass =
                                (
                                    ReflectionCompat.tryFindClass(
                                        "com.android.settings.development.AdbWirelessDebuggingFragment",
                                        classLoader,
                                    ) ?: ReflectionCompat.tryFindClass(
                                        "com.android.settings.development.WirelessDebuggingFragment",
                                        classLoader,
                                    )
                                )?.name ?: "com.android.settings.development.WirelessDebuggingFragment"
                            val intent = Intent(context, subSettingsClass)
                            intent.putExtra(":settings:show_fragment", fragmentClass)
                            context.startActivity(intent)
                        }
                    } catch (e: android.content.ActivityNotFoundException) {
                        module.log(Log.WARN, TAG, "HotspotAdb: failed to open Wireless Debugging screen: $e")
                    } catch (e: SecurityException) {
                        module.log(Log.WARN, TAG, "HotspotAdb: failed to open Wireless Debugging screen: $e")
                    } catch (e: Exception) {
                        module.log(Log.WARN, TAG, "HotspotAdb: failed to open Wireless Debugging screen: $e")
                    }
                    true
                }
            callMethod(pref, "setOnPreferenceClickListener", clickProxy)
        }

        callMethod(screen, "addPreference", pref)
        module.log(Log.INFO, TAG, "HotspotAdb: injected wireless debugging toggle into hotspot settings")
        return pref
    }

    private fun registerListenersIfNeeded(
        fragment: Any,
        context: Context,
        pref: Any,
        module: XposedModule,
    ) {
        setFragmentExtra(fragment, "hotspot_adb_context", context)

        if (getFragmentExtra(fragment, "hotspot_adb_observer") == null) {
            val handler = Handler(Looper.getMainLooper())
            val uri = Settings.Global.getUriFor(ADB_WIFI_ENABLED)
            val observer =
                object : ContentObserver(handler) {
                    override fun onChange(
                        selfChange: Boolean,
                        uri: Uri?,
                    ) {
                        val on = isAdbWifiEnabled(context) && HotspotHelper.isHotspotActive(context)
                        callMethod(pref, "setChecked", on)
                        callMethod(pref, "setSummary", getWirelessDebuggingSummary(context, on) as CharSequence)
                    }
                }
            context.contentResolver.registerContentObserver(uri, false, observer)
            setFragmentExtra(fragment, "hotspot_adb_observer", observer)
            module.log(Log.DEBUG, TAG, "HotspotAdb: registered ContentObserver for WifiTetherSettings")
        }

        if (getFragmentExtra(fragment, "hotspot_adb_receiver") == null) {
            val handler = Handler(Looper.getMainLooper())
            val updatePref =
                Runnable {
                    val on = isAdbWifiEnabled(context) && HotspotHelper.isHotspotActive(context)
                    callMethod(pref, "setChecked", on)
                    callMethod(pref, "setSummary", getWirelessDebuggingSummary(context, on) as CharSequence)
                }
            val receiver =
                object : BroadcastReceiver() {
                    override fun onReceive(
                        ctx: Context,
                        intent: Intent,
                    ) {
                        updatePref.run()
                        handler.postDelayed(updatePref, 1000)
                    }
                }
            context.registerReceiver(
                receiver,
                IntentFilter(WifiManager.WIFI_STATE_CHANGED_ACTION).apply {
                    addAction(WIFI_AP_STATE_CHANGED_ACTION)
                },
            )
            setFragmentExtra(fragment, "hotspot_adb_receiver", receiver)
            setFragmentExtra(fragment, "hotspot_adb_handler", handler)
            setFragmentExtra(fragment, "hotspot_adb_runnable", updatePref)
            module.log(Log.DEBUG, TAG, "HotspotAdb: registered BroadcastReceiver for WifiTetherSettings")
        }
    }

    private fun cleanupFragment(
        fragment: Any,
        module: XposedModule,
    ) {
        val extras = removeFragmentExtras(fragment) ?: return

        val context = extras["hotspot_adb_context"] as? Context
        val observer = extras["hotspot_adb_observer"] as? ContentObserver
        val receiver = extras["hotspot_adb_receiver"] as? BroadcastReceiver
        val handler = extras["hotspot_adb_handler"] as? Handler
        val runnable = extras["hotspot_adb_runnable"] as? Runnable

        if (runnable != null) handler?.removeCallbacks(runnable)
        handler?.removeCallbacksAndMessages(null)

        if (context != null) {
            if (observer != null) {
                try {
                    context.contentResolver.unregisterContentObserver(observer)
                } catch (e: SecurityException) {
                    Log.d(TAG, "HotspotAdb: unregisterContentObserver failed: $e")
                } catch (e: IllegalArgumentException) {
                    Log.d(TAG, "HotspotAdb: unregisterContentObserver failed: $e")
                }
            }
            if (receiver != null) {
                try {
                    context.unregisterReceiver(receiver)
                } catch (e: IllegalArgumentException) {
                    Log.d(TAG, "HotspotAdb: unregisterReceiver failed: $e")
                }
            }
        }

        module.log(Log.DEBUG, TAG, "HotspotAdb: cleaned up listeners for WifiTetherSettings")
    }

    private fun isAdbWifiEnabled(context: Context): Boolean = Settings.Global.getInt(context.contentResolver, ADB_WIFI_ENABLED, 0) == 1

    private fun getWirelessDebuggingSummary(
        context: Context,
        enabled: Boolean,
    ): String {
        if (!enabled) return ""
        val ip =
            HotspotHelper.getHotspotIpAddress(context)
                ?: HotspotHelper.getAnyWlanIp()
                ?: return ""
        val port = getAdbWirelessPort()
        return if (port > 0) "Host AP IP: $ip:$port" else "Host AP IP: $ip"
    }

    private fun getAdbWirelessPort(): Int =
        try {
            val serviceManagerClass = Class.forName("android.os.ServiceManager")
            val binder = serviceManagerClass.getMethod("getService", String::class.java).invoke(null, "adb")
            val stub = Class.forName("android.debug.IAdbManager\$Stub")
            val adbService = stub.getMethod("asInterface", android.os.IBinder::class.java).invoke(null, binder)
            adbService.javaClass.getMethod("getAdbWirelessPort").invoke(adbService) as Int
        } catch (_: Throwable) {
            -1
        }

    private fun tryGetMethod(
        clazz: Class<*>,
        name: String,
        vararg params: Class<*>,
    ): Method? =
        try {
            clazz.getDeclaredMethod(name, *params).also { it.isAccessible = true }
        } catch (_: NoSuchMethodException) {
            null
        }

    @Suppress("SpreadOperator")
    private fun callMethod(
        obj: Any,
        name: String,
        vararg args: Any?,
    ): Any? =
        try {
            val cacheKey = "${obj.javaClass.name}#$name#${args.joinToString { it?.javaClass?.name ?: "null" }}"
            val method =
                synchronized(methodCache) {
                    methodCache.getOrPut(cacheKey) {
                        ReflectionCompat.findCompatibleMethod(obj.javaClass, name, args)
                            ?: throw NoSuchMethodException(
                                "${obj.javaClass.name}.$name(${args.joinToString { it?.javaClass?.simpleName ?: "null" }})",
                            )
                    }
                }
            method.invoke(obj, *args)
        } catch (e: ReflectiveOperationException) {
            Log.w(TAG, "HotspotAdb: callMethod($name) failed: $e")
            null
        } catch (e: IllegalArgumentException) {
            Log.w(TAG, "HotspotAdb: callMethod($name) failed: $e")
            null
        }

    private fun setFragmentExtra(
        obj: Any,
        key: String,
        value: Any?,
    ) {
        synchronized(fragmentExtras) {
            fragmentExtras.getOrPut(obj) { mutableMapOf() }[key] = value
        }
    }

    private fun getFragmentExtra(
        obj: Any,
        key: String,
    ): Any? =
        synchronized(fragmentExtras) {
            fragmentExtras[obj]?.get(key)
        }

    private fun removeFragmentExtras(obj: Any): MutableMap<String, Any?>? =
        synchronized(fragmentExtras) {
            fragmentExtras.remove(obj)
        }

    private const val TAG = HotspotAdbModule.TAG
}
