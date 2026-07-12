package io.drsr.hotspotadb

import android.util.Log
import io.drsr.hotspotadb.compat.SystemContextCompat
import io.github.libxposed.api.XposedModule
import io.github.libxposed.api.XposedModuleInterface.ModuleLoadedParam
import io.github.libxposed.api.XposedModuleInterface.PackageLoadedParam
import io.github.libxposed.api.XposedModuleInterface.SystemServerStartingParam

/** Modern libxposed API 101 entry point. */
class HotspotAdbModule : XposedModule() {
    companion object {
        const val TAG = "HotspotAdb"
    }

    override fun onModuleLoaded(param: ModuleLoadedParam) {
        log(Log.INFO, TAG, "HotspotAdb: module loaded in ${param.processName}")
        log(Log.INFO, TAG, "HotspotAdb: framework $frameworkName $frameworkVersion (API $apiVersion)")
    }

    override fun onSystemServerStarting(param: SystemServerStartingParam) {
        log(Log.INFO, TAG, "HotspotAdb: installing framework compatibility")
        FixedEndpointController.configure(param.classLoader, this)
        val systemContext = SystemContextCompat.getSystemContext(param.classLoader)
        if (systemContext != null) {
            FixedEndpointController.onContextAvailable(systemContext)
        }
        FrameworkHook.install(param.classLoader, this)
        Qpr1Hook.install(param.classLoader, this)
    }

    override fun onPackageLoaded(param: PackageLoadedParam) {
        if (param.packageName == "com.android.settings") {
            log(Log.INFO, TAG, "HotspotAdb: installing Settings compatibility")
            SettingsHook.install(param.defaultClassLoader, this)
        }
    }
}
