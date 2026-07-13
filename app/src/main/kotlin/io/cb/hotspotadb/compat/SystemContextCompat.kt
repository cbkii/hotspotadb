package io.cb.hotspotadb.compat

import android.content.Context

/** Best-effort access to system_server's long-lived system context. */
object SystemContextCompat {
    fun getSystemContext(classLoader: ClassLoader): Context? {
        return try {
            val activityThread = Class.forName("android.app.ActivityThread", false, classLoader)
            val current = activityThread.getMethod("currentActivityThread").invoke(null) ?: return null
            activityThread.getMethod("getSystemContext").invoke(current) as? Context
        } catch (_: ReflectiveOperationException) {
            null
        } catch (_: SecurityException) {
            null
        }
    }
}
