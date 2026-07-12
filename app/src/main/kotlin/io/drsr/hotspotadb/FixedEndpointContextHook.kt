package io.drsr.hotspotadb

import io.drsr.hotspotadb.compat.AdbFrameworkRefs
import io.drsr.hotspotadb.compat.AdbHandlerContextCompat
import io.github.libxposed.api.XposedModule

/** Captures system_server context on the ADB path shared by Android 15 and 16. */
object FixedEndpointContextHook {
    fun install(
        classLoader: ClassLoader,
        module: XposedModule,
    ) {
        val reporter = HookReporter("system_server-fixed-endpoint", module)
        val handlerClass = AdbFrameworkRefs.findHandlerClass(classLoader, module)
        if (handlerClass == null) {
            reporter.report("Fixed endpoint context", "AdbDebuggingHandler", Status.MISSING, "class not found")
            reporter.summarize()
            return
        }

        val method =
            ReflectionCompat.findMethod(
                handlerClass,
                module,
                "Fixed endpoint context",
                "getCurrentWifiApInfo",
                includeInherited = true,
            )
        if (method == null) {
            reporter.report("Fixed endpoint context", "getCurrentWifiApInfo", Status.MISSING, "method not found")
            reporter.summarize()
            return
        }

        module.deoptimize(method)
        module.hook(method).intercept { chain ->
            val context = AdbHandlerContextCompat.getContext(chain.getThisObject())
            val result = chain.proceed()
            if (context != null) {
                FixedEndpointController.onContextAvailable(context)
            }
            result
        }
        reporter.report("Fixed endpoint context", "getCurrentWifiApInfo", Status.INSTALLED, handlerClass.name)
        reporter.summarize()
    }
}
