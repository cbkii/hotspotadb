package io.drsr.hotspotadb

import de.robv.android.xposed.IXposedHookLoadPackage
import de.robv.android.xposed.XposedBridge
import de.robv.android.xposed.callbacks.XC_LoadPackage

class HotspotAdbModule : IXposedHookLoadPackage {
    override fun handleLoadPackage(lpparam: XC_LoadPackage.LoadPackageParam) {
        XposedBridge.log("HotspotAdb: handleLoadPackage ${lpparam.packageName} / ${lpparam.processName}")
        when (lpparam.packageName) {
            "com.android.settings" -> {
                XposedBridge.log("HotspotAdb: hooking Settings")
                SettingsHook.init(lpparam)
            }
            "android" -> {
                XposedBridge.log("HotspotAdb: hooking framework")
                FrameworkHook.init(lpparam)
            }
        }
    }
}
