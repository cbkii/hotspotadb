package io.drsr.hotspotadb.compat

import android.content.Context
import io.drsr.hotspotadb.ReflectionCompat

/** Extracts system_server context from nested or top-level ADB handler layouts. */
object AdbHandlerContextCompat {
    fun getContext(handler: Any?): Context? {
        handler ?: return null
        ReflectionCompat.getFieldValueByName(handler, "mContext")?.let { return it as? Context }
        val manager =
            ReflectionCompat.getFieldValueByName(handler, "this\$0")
                ?: ReflectionCompat.getFieldValueByName(handler, "mAdbDebuggingManager")
                ?: ReflectionCompat.getFieldValueByType(handler, "com.android.server.adb.AdbDebuggingManager")
        return manager?.let { ReflectionCompat.getFieldValueByName(it, "mContext") as? Context }
    }
}
