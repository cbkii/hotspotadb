package io.drsr.hotspotadb

import android.util.Log
import io.github.libxposed.api.XposedModule

enum class Status {
    INSTALLED,
    SKIPPED,
    MISSING,
    FAILED,
}

data class HookProbeResult(
    val area: String,
    val target: String,
    val status: Status,
    val detail: String,
)

class HookReporter(private val processName: String, private val module: XposedModule) {
    private val results = mutableListOf<HookProbeResult>()

    fun report(
        area: String,
        target: String,
        status: Status,
        detail: String,
    ) {
        results.add(HookProbeResult(area, target, status, detail))
    }

    fun summarize() {
        if (results.isEmpty()) return
        module.log(Log.INFO, HotspotAdbModule.TAG, "HotspotAdb: === Hook Install Summary for $processName ===")
        results.forEach {
            module.log(Log.INFO, HotspotAdbModule.TAG, "HotspotAdb:   [${it.status.name}] ${it.area} - ${it.target} (${it.detail})")
        }
        module.log(Log.INFO, HotspotAdbModule.TAG, "HotspotAdb: =========================================")
    }
}
