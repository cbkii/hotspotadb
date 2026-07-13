package io.cb.hotspotadb

import android.util.Log
import io.cb.hotspotadb.compat.AdbFrameworkRefs
import io.cb.hotspotadb.compat.AdbHandlerContextCompat
import io.github.libxposed.api.XposedModule

/** Android 16 QPR1 compatibility for the verifyWifiNetwork trust gate. */
object Qpr1Hook {
    fun install(
        classLoader: ClassLoader,
        module: XposedModule,
    ) {
        val reporter = HookReporter("system_server-qpr1", module)
        val handlerClass = AdbFrameworkRefs.findHandlerClass(classLoader, module)
        if (handlerClass == null) {
            reporter.report("QPR1 trust gate", "AdbDebuggingHandler", Status.MISSING, "class not found")
            reporter.summarize()
            return
        }

        val method =
            ReflectionCompat.findMethod(
                handlerClass,
                module,
                "QPR1 trust gate",
                "verifyWifiNetwork",
                includeInherited = true,
                String::class.java,
                String::class.java,
            )
        if (method == null) {
            reporter.report("QPR1 trust gate", "verifyWifiNetwork", Status.SKIPPED, "method absent on this build")
            reporter.summarize()
            return
        }

        module.deoptimize(method)
        module.hook(method).intercept { chain ->
            val context = AdbHandlerContextCompat.getContext(chain.getThisObject())
            if (context == null) {
                module.log(Log.WARN, HotspotAdbModule.TAG, "HotspotAdb: verifyWifiNetwork context unavailable; pass-through")
                return@intercept chain.proceed()
            }

            FixedEndpointController.onContextAvailable(context)
            if (HotspotHelper.isHotspotActive(context)) {
                module.log(Log.INFO, HotspotAdbModule.TAG, "HotspotAdb: verifyWifiNetwork -> true (hotspot active)")
                true
            } else {
                chain.proceed()
            }
        }
        reporter.report("QPR1 trust gate", "verifyWifiNetwork", Status.INSTALLED, "hotspot accepted as trusted")
        reporter.summarize()
    }
}
