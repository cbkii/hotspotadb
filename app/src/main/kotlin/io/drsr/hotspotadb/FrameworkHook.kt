package io.drsr.hotspotadb

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.database.ContentObserver
import android.net.Uri
import android.net.wifi.WifiManager
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import de.robv.android.xposed.XC_MethodHook
import de.robv.android.xposed.XposedBridge
import de.robv.android.xposed.XposedHelpers
import de.robv.android.xposed.callbacks.XC_LoadPackage

object FrameworkHook {
    private const val ADB_WIFI_ENABLED = "adb_wifi_enabled"

    @Volatile
    private var observersRegistered = false

    fun init(lpparam: XC_LoadPackage.LoadPackageParam) {
        SubnetAlias.setClassLoader(lpparam.classLoader)
        hookGetCurrentWifiApInfo(lpparam)
        hookBroadcastReceiver(lpparam)
    }

    private fun hookGetCurrentWifiApInfo(lpparam: XC_LoadPackage.LoadPackageParam) {
        try {
            val handlerClass =
                XposedHelpers.findClass(
                    "com.android.server.adb.AdbDebuggingManager\$AdbDebuggingHandler",
                    lpparam.classLoader,
                )

            XposedHelpers.findAndHookMethod(
                handlerClass,
                "getCurrentWifiApInfo",
                object : XC_MethodHook() {
                    override fun afterHookedMethod(param: MethodHookParam) {
                        if (param.result != null) return

                        val context = getContext(param.thisObject) ?: return
                        if (!HotspotHelper.isHotspotActive(context)) return

                        try {
                            val ssid =
                                try {
                                    val wm = context.getSystemService(Context.WIFI_SERVICE) as WifiManager
                                    val config = wm.javaClass.getMethod("getSoftApConfiguration").invoke(wm)
                                    val wifiSsid = config.javaClass.getMethod("getWifiSsid").invoke(config)
                                    wifiSsid?.toString() ?: "HotspotAP"
                                } catch (_: Throwable) {
                                    "HotspotAP"
                                }

                            // Android 16+: top-level class; Android 15: inner class
                            val connectionInfoClass =
                                try {
                                    XposedHelpers.findClass(
                                        "com.android.server.adb.AdbConnectionInfo",
                                        lpparam.classLoader,
                                    )
                                } catch (_: XposedHelpers.ClassNotFoundError) {
                                    XposedHelpers.findClass(
                                        "com.android.server.adb.AdbDebuggingManager\$AdbConnectionInfo",
                                        lpparam.classLoader,
                                    )
                                }
                            val info =
                                XposedHelpers.newInstance(
                                    connectionInfoClass,
                                    "02:00:00:00:00:00",
                                    ssid,
                                )
                            param.result = info
                            XposedBridge.log("HotspotAdb: getCurrentWifiApInfo -> synthetic (hotspot active)")

                            ensureObservers(context)
                            evaluateProxy(context)
                        } catch (e: Exception) {
                            XposedBridge.log("HotspotAdb: failed to create AdbConnectionInfo: $e")
                        }
                    }
                },
            )
        } catch (e: Exception) {
            XposedBridge.log("HotspotAdb: failed to hook getCurrentWifiApInfo: $e")
        }
    }

    private fun ensureObservers(context: Context) {
        if (observersRegistered) return
        synchronized(this) {
            if (observersRegistered) return
            try {
                val resolver = context.contentResolver
                val observer =
                    object : ContentObserver(Handler(Looper.getMainLooper())) {
                        override fun onChange(
                            selfChange: Boolean,
                            uri: Uri?,
                        ) {
                            evaluateProxy(context)
                        }
                    }
                resolver.registerContentObserver(
                    Settings.Global.getUriFor(HotspotHelper.FIXED_ENDPOINT_KEY),
                    false,
                    observer,
                )
                resolver.registerContentObserver(
                    Settings.Global.getUriFor(ADB_WIFI_ENABLED),
                    false,
                    observer,
                )
                observersRegistered = true
                XposedBridge.log("HotspotAdb: framework observers registered")
            } catch (e: Exception) {
                XposedBridge.log("HotspotAdb: failed to register observers: $e")
            }
        }
    }

    private fun evaluateProxy(context: Context) {
        try {
            val hotspot = HotspotHelper.isHotspotActive(context)
            val fixed = HotspotHelper.isFixedEndpointEnabled(context)
            val adb = isAdbWifiEnabled(context)

            if (hotspot && fixed) SubnetAlias.apply(context) else SubnetAlias.remove()

            if (hotspot && fixed && adb) {
                val realPort = getAdbWirelessPort()
                if (realPort > 0) AdbPortProxy.start(realPort) else AdbPortProxy.stop()
            } else {
                AdbPortProxy.stop()
            }
        } catch (e: Exception) {
            XposedBridge.log("HotspotAdb: evaluateProxy failed: $e")
        }
    }

    private fun isAdbWifiEnabled(context: Context): Boolean {
        return Settings.Global.getInt(context.contentResolver, ADB_WIFI_ENABLED, 0) == 1
    }

    private fun getAdbWirelessPort(): Int {
        return try {
            val serviceManagerClass = Class.forName("android.os.ServiceManager")
            val binder =
                serviceManagerClass.getMethod("getService", String::class.java)
                    .invoke(null, "adb")
            val iAdbManagerStub = Class.forName("android.debug.IAdbManager\$Stub")
            val adbService =
                iAdbManagerStub.getMethod("asInterface", android.os.IBinder::class.java)
                    .invoke(null, binder)
            adbService.javaClass.getMethod("getAdbWirelessPort").invoke(adbService) as Int
        } catch (_: Throwable) {
            -1
        }
    }

    private fun hookBroadcastReceiver(lpparam: XC_LoadPackage.LoadPackageParam) {
        var found = false

        // Android 16+: BroadcastReceiver extracted to a top-level class
        try {
            val cls =
                XposedHelpers.findClass(
                    "com.android.server.adb.AdbBroadcastReceiver",
                    lpparam.classLoader,
                )
            hookBroadcastReceiverClass(cls)
            found = true
            XposedBridge.log("HotspotAdb: hooked BroadcastReceiver ${cls.name}")
        } catch (_: XposedHelpers.ClassNotFoundError) {
            // Not Android 16+, try legacy inner-class scan below
        } catch (e: Exception) {
            XposedBridge.log("HotspotAdb: error hooking AdbBroadcastReceiver: $e")
        }

        // Android 15: scan anonymous inner classes of AdbDebuggingHandler
        if (!found) {
            val baseName = "com.android.server.adb.AdbDebuggingManager\$AdbDebuggingHandler"
            for (i in 1..10) {
                try {
                    val cls = Class.forName("$baseName\$$i", false, lpparam.classLoader)
                    if (!BroadcastReceiver::class.java.isAssignableFrom(cls)) continue

                    hookBroadcastReceiverClass(cls)
                    found = true
                    XposedBridge.log("HotspotAdb: hooked BroadcastReceiver ${cls.name}")
                    break
                } catch (_: ClassNotFoundException) {
                    continue
                } catch (e: Exception) {
                    XposedBridge.log("HotspotAdb: error scanning inner class $i: $e")
                }
            }
        }

        if (!found) {
            XposedBridge.log("HotspotAdb: BroadcastReceiver not found, falling back to ContentResolver hook")
            hookSettingsGlobalDisable(lpparam)
        }
    }

    private fun hookBroadcastReceiverClass(cls: Class<*>) {
        XposedBridge.hookAllMethods(
            cls,
            "onReceive",
            object : XC_MethodHook() {
                override fun beforeHookedMethod(param: MethodHookParam) {
                    val context = param.args[0] as Context
                    val intent = param.args[1] as Intent
                    val action = intent.action ?: return

                    if (action == WifiManager.WIFI_STATE_CHANGED_ACTION ||
                        action == WifiManager.NETWORK_STATE_CHANGED_ACTION
                    ) {
                        if (HotspotHelper.isHotspotActive(context)) {
                            param.result = null
                            XposedBridge.log("HotspotAdb: suppressed $action (hotspot active)")
                        }
                    }
                }

                override fun afterHookedMethod(param: MethodHookParam) {
                    val context = param.args[0] as? Context ?: return
                    ensureObservers(context)
                    evaluateProxy(context)
                }
            },
        )
    }

    private fun hookSettingsGlobalDisable(lpparam: XC_LoadPackage.LoadPackageParam) {
        // Fallback: intercept Settings.Global.putInt to prevent ADB_WIFI_ENABLED = 0 when hotspot is active
        try {
            XposedHelpers.findAndHookMethod(
                "android.provider.Settings\$Global",
                lpparam.classLoader,
                "putInt",
                android.content.ContentResolver::class.java,
                String::class.java,
                Int::class.javaPrimitiveType,
                object : XC_MethodHook() {
                    override fun beforeHookedMethod(param: MethodHookParam) {
                        val key = param.args[1] as? String ?: return
                        val value = param.args[2] as Int
                        if (key == "adb_wifi_enabled" && value == 0) {
                            try {
                                val resolver = param.args[0] as android.content.ContentResolver
                                // Android 15: getContext(); Android 16: mContext field
                                val context =
                                    try {
                                        resolver.javaClass.getMethod("getContext")
                                            .invoke(resolver) as? Context
                                    } catch (_: NoSuchMethodException) {
                                        val field =
                                            android.content.ContentResolver::class.java
                                                .getDeclaredField("mContext")
                                        field.isAccessible = true
                                        field.get(resolver) as? Context
                                    }
                                if (context != null && HotspotHelper.isHotspotActive(context)) {
                                    param.result = false
                                    XposedBridge.log("HotspotAdb: blocked ADB_WIFI_ENABLED=0 (hotspot active)")
                                }
                            } catch (e: Exception) {
                                XposedBridge.log("HotspotAdb: failed to get context from ContentResolver: $e")
                            }
                        }
                    }
                },
            )
        } catch (e: Exception) {
            XposedBridge.log("HotspotAdb: failed to hook Settings.Global.putInt: $e")
        }
    }

    private fun getContext(handler: Any): Context? {
        return try {
            val manager = XposedHelpers.getObjectField(handler, "this\$0")
            XposedHelpers.getObjectField(manager, "mContext") as Context
        } catch (e: Exception) {
            XposedBridge.log("HotspotAdb: failed to get context: $e")
            null
        }
    }
}
