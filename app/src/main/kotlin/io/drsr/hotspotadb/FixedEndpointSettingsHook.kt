package io.drsr.hotspotadb

import android.content.Context
import android.database.ContentObserver
import android.net.Uri
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.util.Log
import io.drsr.hotspotadb.compat.SettingsAppRefs
import io.github.libxposed.api.XposedModule
import java.lang.ref.WeakReference
import java.lang.reflect.Proxy
import java.util.Collections
import java.util.WeakHashMap

/** Settings-scope hooks for the optional fixed hotspot endpoint. */
object FixedEndpointSettingsHook {
    private data class FragmentState(
        val context: Context,
        val observer: ContentObserver,
    )

    private val fragmentStates: MutableMap<Any, FragmentState> =
        Collections.synchronizedMap(WeakHashMap())

    fun install(
        classLoader: ClassLoader,
        module: XposedModule,
    ) {
        val reporter = HookReporter("com.android.settings-fixed-endpoint", module)
        hookDisplayedIp(classLoader, module, reporter)
        hookDisplayedPort(classLoader, module, reporter)
        hookFixedEndpointPreference(classLoader, module, reporter)
        reporter.summarize()
    }

    private fun hookDisplayedIp(
        classLoader: ClassLoader,
        module: XposedModule,
        reporter: HookReporter,
    ) {
        val controller =
            ReflectionCompat.findFirstClass(
                classLoader,
                module,
                "Fixed endpoint IPv4 controller",
                "com.android.settings.development.AdbIpAddressPreferenceController",
            ) ?: run {
                reporter.report("Fixed endpoint", "getIpv4Address", Status.MISSING, "controller absent")
                return
            }
        val method =
            ReflectionCompat.findMethod(
                controller,
                module,
                "Fixed endpoint IPv4",
                "getIpv4Address",
                includeInherited = true,
            ) ?: run {
                reporter.report("Fixed endpoint", "getIpv4Address", Status.MISSING, "method absent")
                return
            }
        module.hook(method).intercept { chain ->
            val instance = chain.getThisObject() ?: return@intercept chain.proceed()
            val context = ReflectionCompat.getFieldValueByName(instance, "mContext") as? Context
            if (context != null && HotspotHelper.isFixedEndpointReady(context)) {
                HotspotHelper.FIXED_IP
            } else {
                chain.proceed()
            }
        }
        reporter.report("Fixed endpoint", "getIpv4Address", Status.INSTALLED, "ready-state override")
    }

    private fun hookDisplayedPort(
        classLoader: ClassLoader,
        module: XposedModule,
        reporter: HookReporter,
    ) {
        val proxyClass =
            ReflectionCompat.findFirstClass(
                classLoader,
                module,
                "Fixed endpoint ADB binder proxy",
                "android.debug.IAdbManager\$Stub\$Proxy",
            ) ?: run {
                reporter.report("Fixed endpoint", "getAdbWirelessPort", Status.MISSING, "binder proxy absent")
                return
            }
        val method =
            ReflectionCompat.findMethod(
                proxyClass,
                module,
                "Fixed endpoint ADB port",
                "getAdbWirelessPort",
                includeInherited = true,
            ) ?: run {
                reporter.report("Fixed endpoint", "getAdbWirelessPort", Status.MISSING, "method absent")
                return
            }
        module.hook(method).intercept { chain ->
            val context = currentApplicationContext()
            if (context != null && HotspotHelper.isFixedEndpointReady(context)) {
                HotspotHelper.FIXED_PORT
            } else {
                chain.proceed()
            }
        }
        reporter.report("Fixed endpoint", "getAdbWirelessPort", Status.INSTALLED, "ready-state override")
    }

    private fun hookFixedEndpointPreference(
        classLoader: ClassLoader,
        module: XposedModule,
        reporter: HookReporter,
    ) {
        val fragmentClass = SettingsAppRefs.findWirelessDebuggingFragmentClass(classLoader, module)
        if (fragmentClass == null) {
            reporter.report("Fixed endpoint UI", "WirelessDebuggingFragment", Status.MISSING, "fragment absent")
            return
        }
        val onStart =
            ReflectionCompat.findMethod(
                fragmentClass,
                module,
                "Fixed endpoint UI",
                "onStart",
                includeInherited = true,
            )
        val onStop =
            ReflectionCompat.findMethod(
                fragmentClass,
                module,
                "Fixed endpoint UI",
                "onStop",
                includeInherited = true,
            )
        if (onStart == null || onStop == null) {
            reporter.report("Fixed endpoint UI", "onStart/onStop", Status.MISSING, "lifecycle method absent")
            return
        }

        module.hook(onStart).intercept { chain ->
            val result = chain.proceed()
            val fragment = chain.getThisObject()
            if (fragment != null && fragmentClass.isInstance(fragment)) {
                runCatching { injectPreference(fragment, classLoader, module) }
                    .onFailure {
                        module.log(
                            Log.ERROR,
                            HotspotAdbModule.TAG,
                            "HotspotAdb: fixed endpoint UI injection failed: $it",
                        )
                    }
            }
            result
        }
        module.hook(onStop).intercept { chain ->
            val fragment = chain.getThisObject()
            if (fragment != null && fragmentClass.isInstance(fragment)) {
                cleanup(fragment, module)
            }
            chain.proceed()
        }
        reporter.report("Fixed endpoint UI", "onStart/onStop", Status.INSTALLED, fragmentClass.name)
    }

    private fun injectPreference(
        fragment: Any,
        classLoader: ClassLoader,
        module: XposedModule,
    ) {
        val screen = callMethod(fragment, "getPreferenceScreen") ?: return
        val context = callMethod(screen, "getContext") as? Context ?: return
        val existing = callMethod(screen, "findPreference", HotspotHelper.FIXED_ENDPOINT_KEY)
        val preference = existing ?: createPreference(screen, fragment, context, classLoader, module) ?: return
        updatePreference(context, preference)
        registerObserver(fragment, context, preference, module)
    }

    private fun createPreference(
        screen: Any,
        fragment: Any,
        context: Context,
        classLoader: ClassLoader,
        module: XposedModule,
    ): Any? {
        val switchClass =
            ReflectionCompat.tryFindClass("androidx.preference.SwitchPreferenceCompat", classLoader) ?: run {
                module.log(Log.WARN, HotspotAdbModule.TAG, "HotspotAdb: SwitchPreferenceCompat unavailable")
                return null
            }
        val preference = switchClass.getConstructor(Context::class.java).newInstance(context)
        callMethod(preference, "setKey", HotspotHelper.FIXED_ENDPOINT_KEY)
        callMethod(preference, "setTitle", "Fixed hotspot endpoint" as CharSequence)

        val listenerClass =
            ReflectionCompat.tryFindClass("androidx.preference.Preference\$OnPreferenceChangeListener", classLoader) ?: return null
        val listener =
            Proxy.newProxyInstance(classLoader, arrayOf(listenerClass)) { _, _, args ->
                val enabled = args?.getOrNull(1) as? Boolean ?: false
                Settings.Global.putInt(
                    context.contentResolver,
                    HotspotHelper.FIXED_ENDPOINT_KEY,
                    if (enabled) 1 else 0,
                )
                updatePreference(context, preference)
                runCatching { callMethod(fragment, "updatePreferenceStates") }
                true
            }
        callMethod(preference, "setOnPreferenceChangeListener", listener)
        placeAfterIpPreference(screen, preference)
        callMethod(screen, "addPreference", preference)
        module.log(Log.INFO, HotspotAdbModule.TAG, "HotspotAdb: added fixed hotspot endpoint preference")
        return preference
    }

    private fun placeAfterIpPreference(
        screen: Any,
        preference: Any,
    ) {
        val count = callMethod(screen, "getPreferenceCount") as? Int ?: return
        var targetIndex = 0
        for (index in 0 until count) {
            val candidate = callMethod(screen, "getPreference", index) ?: continue
            if (callMethod(candidate, "getKey") as? String == SettingsAppRefs.IP_PREF_KEY) {
                targetIndex = index
                break
            }
        }
        for (index in 0 until count) {
            val candidate = callMethod(screen, "getPreference", index) ?: continue
            val order = if (index <= targetIndex) index else index + 1
            callMethod(candidate, "setOrder", order)
        }
        callMethod(preference, "setOrder", targetIndex + 1)
    }

    private fun updatePreference(
        context: Context,
        preference: Any,
    ) {
        val enabled = HotspotHelper.isFixedEndpointEnabled(context)
        val ready = HotspotHelper.isFixedEndpointReady(context)
        callMethod(preference, "setChecked", enabled)
        val summary =
            when {
                ready -> "Active at ${HotspotHelper.FIXED_IP}:${HotspotHelper.FIXED_PORT}"
                enabled && !HotspotHelper.isAdbWifiEnabled(context) -> "Waiting for Wireless debugging"
                enabled && !HotspotHelper.isHotspotActive(context) -> "Waiting for hotspot"
                enabled -> "Unavailable; dynamic hotspot address remains active"
                else -> "Use ${HotspotHelper.FIXED_IP}:${HotspotHelper.FIXED_PORT} while hotspot is active"
            }
        callMethod(preference, "setSummary", summary as CharSequence)
    }

    private fun registerObserver(
        fragment: Any,
        context: Context,
        preference: Any,
        module: XposedModule,
    ) {
        if (fragmentStates.containsKey(fragment)) return
        val appContext = context.applicationContext ?: context
        val weakPreference = WeakReference(preference)
        val observer =
            object : ContentObserver(Handler(Looper.getMainLooper())) {
                override fun onChange(
                    selfChange: Boolean,
                    uri: Uri?,
                ) {
                    weakPreference.get()?.let { updatePreference(appContext, it) }
                }
            }
        try {
            listOf(
                HotspotHelper.ADB_WIFI_ENABLED,
                HotspotHelper.FIXED_ENDPOINT_KEY,
                HotspotHelper.FIXED_ENDPOINT_READY_KEY,
            ).forEach { key ->
                appContext.contentResolver.registerContentObserver(
                    Settings.Global.getUriFor(key),
                    false,
                    observer,
                )
            }
            fragmentStates[fragment] = FragmentState(appContext, observer)
        } catch (e: RuntimeException) {
            module.log(Log.WARN, HotspotAdbModule.TAG, "HotspotAdb: fixed endpoint UI observer failed: $e")
        }
    }

    private fun cleanup(
        fragment: Any,
        module: XposedModule,
    ) {
        val state = fragmentStates.remove(fragment) ?: return
        try {
            state.context.contentResolver.unregisterContentObserver(state.observer)
        } catch (e: RuntimeException) {
            module.log(Log.DEBUG, HotspotAdbModule.TAG, "HotspotAdb: fixed endpoint UI cleanup ignored: $e")
        }
    }

    private fun currentApplicationContext(): Context? =
        try {
            val activityThread = Class.forName("android.app.ActivityThread")
            activityThread.getMethod("currentApplication").invoke(null) as? Context
        } catch (_: ReflectiveOperationException) {
            null
        } catch (_: SecurityException) {
            null
        }

    @Suppress("SpreadOperator")
    private fun callMethod(
        target: Any,
        name: String,
        vararg args: Any?,
    ): Any? =
        try {
            val method = ReflectionCompat.findCompatibleMethod(target.javaClass, name, args) ?: return null
            method.isAccessible = true
            method.invoke(target, *args)
        } catch (e: ReflectiveOperationException) {
            Log.w(HotspotAdbModule.TAG, "HotspotAdb: fixed endpoint callMethod($name) failed: $e")
            null
        } catch (e: IllegalArgumentException) {
            Log.w(HotspotAdbModule.TAG, "HotspotAdb: fixed endpoint callMethod($name) failed: $e")
            null
        }
}
