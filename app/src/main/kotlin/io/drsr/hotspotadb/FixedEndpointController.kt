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
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

/** Coordinates the fixed subnet alias and TLS-preserving port proxy in system_server. */
object FixedEndpointController {
    private const val WIFI_AP_STATE_CHANGED_ACTION = "android.net.wifi.WIFI_AP_STATE_CHANGED"
    private const val PORT_RETRY_DELAY_MS = 500L
    private const val MAX_PORT_RETRIES = 20

    private val lock = Any()
    private val executor =
        Executors.newSingleThreadScheduledExecutor { runnable ->
            Thread(runnable, "HotspotAdb-FixedEndpoint").apply { isDaemon = true }
        }

    @Volatile
    private var classLoader: ClassLoader? = null

    @Volatile
    private var module: XposedModule? = null

    @Volatile
    private var context: Context? = null

    @Volatile
    private var contentObserversRegistered = false

    @Volatile
    private var hotspotReceiverRegistered = false

    @Volatile
    private var lastState: String? = null

    private var portRetryCount = 0

    fun configure(
        classLoader: ClassLoader,
        module: XposedModule,
    ) {
        this.classLoader = classLoader
        this.module = module
    }

    fun onContextAvailable(context: Context) {
        val stableContext = context.applicationContext ?: context
        this.context = stableContext
        ensureObservers(stableContext)
        scheduleEvaluation()
    }

    private fun ensureObservers(context: Context) {
        synchronized(lock) {
            if (!contentObserversRegistered) {
                val observer =
                    object : ContentObserver(Handler(Looper.getMainLooper())) {
                        override fun onChange(
                            selfChange: Boolean,
                            uri: Uri?,
                        ) {
                            scheduleEvaluation()
                        }
                    }
                try {
                    context.contentResolver.registerContentObserver(
                        Settings.Global.getUriFor(HotspotHelper.ADB_WIFI_ENABLED),
                        false,
                        observer,
                    )
                    context.contentResolver.registerContentObserver(
                        Settings.Global.getUriFor(HotspotHelper.FIXED_ENDPOINT_KEY),
                        false,
                        observer,
                    )
                    contentObserversRegistered = true
                    module?.log(Log.INFO, HotspotAdbModule.TAG, "HotspotAdb: fixed endpoint setting observers registered")
                } catch (e: RuntimeException) {
                    module?.log(Log.WARN, HotspotAdbModule.TAG, "HotspotAdb: fixed endpoint observer registration failed: $e")
                }
            }

            if (!hotspotReceiverRegistered) {
                val receiver =
                    object : BroadcastReceiver() {
                        override fun onReceive(
                            receiverContext: Context,
                            intent: Intent,
                        ) {
                            if (intent.action != null) scheduleEvaluation()
                        }
                    }
                try {
                    val filter =
                        IntentFilter(WifiManager.WIFI_STATE_CHANGED_ACTION).apply {
                            addAction(WIFI_AP_STATE_CHANGED_ACTION)
                        }
                    context.registerReceiver(receiver, filter, Context.RECEIVER_EXPORTED)
                    hotspotReceiverRegistered = true
                    module?.log(Log.INFO, HotspotAdbModule.TAG, "HotspotAdb: fixed endpoint hotspot receiver registered")
                } catch (e: RuntimeException) {
                    module?.log(Log.WARN, HotspotAdbModule.TAG, "HotspotAdb: fixed endpoint receiver registration failed: $e")
                }
            }
        }
    }

    private fun scheduleEvaluation(delayMs: Long = 0L) {
        executor.schedule(
            {
                try {
                    evaluate()
                } catch (e: Throwable) {
                    val ctx = context
                    module?.log(Log.ERROR, HotspotAdbModule.TAG, "HotspotAdb: fixed endpoint evaluation failed: $e")
                    if (ctx != null) {
                        runCatching { HotspotHelper.setFixedEndpointReady(ctx, false) }
                    }
                }
            },
            delayMs,
            TimeUnit.MILLISECONDS,
        )
    }

    private fun evaluate() {
        val ctx = context ?: return
        val loader = classLoader ?: return
        val xposedModule = module ?: return

        val hotspot = HotspotHelper.isHotspotActive(ctx)
        val enabled = HotspotHelper.isFixedEndpointEnabled(ctx)
        val adbEnabled = HotspotHelper.isAdbWifiEnabled(ctx)
        val realPort = if (adbEnabled) HotspotHelper.getAdbWirelessPort() else -1
        val state = "hotspot=$hotspot enabled=$enabled adb=$adbEnabled realPort=$realPort"
        if (state != lastState) {
            xposedModule.log(Log.INFO, HotspotAdbModule.TAG, "HotspotAdb: fixed endpoint state $state")
            lastState = state
        }

        if (!hotspot || !enabled || !adbEnabled) {
            portRetryCount = 0
            HotspotHelper.setFixedEndpointReady(ctx, false)
            AdbPortProxy.stop(xposedModule)
            val aliasRemoved = SubnetAlias.remove(loader, xposedModule)
            if (!aliasRemoved) {
                schedulePortRetry(xposedModule, "alias cleanup failed")
            }
            return
        }

        if (realPort <= 0) {
            HotspotHelper.setFixedEndpointReady(ctx, false)
            AdbPortProxy.stop(xposedModule)
            SubnetAlias.remove(loader, xposedModule)
            schedulePortRetry(xposedModule, "adbd TLS port unavailable")
            return
        }

        portRetryCount = 0
        val aliasReady = SubnetAlias.apply(ctx, loader, xposedModule)
        val proxyReady = aliasReady && AdbPortProxy.start(realPort, xposedModule)
        HotspotHelper.setFixedEndpointReady(ctx, proxyReady)
        if (!proxyReady) {
            AdbPortProxy.stop(xposedModule)
            SubnetAlias.remove(loader, xposedModule)
            schedulePortRetry(xposedModule, "alias or proxy startup failed")
        }
    }

    private fun schedulePortRetry(
        xposedModule: XposedModule,
        reason: String,
    ) {
        if (portRetryCount >= MAX_PORT_RETRIES) {
            if (portRetryCount == MAX_PORT_RETRIES) {
                xposedModule.log(
                    Log.WARN,
                    HotspotAdbModule.TAG,
                    "HotspotAdb: fixed endpoint retry limit reached: $reason",
                )
                portRetryCount++
            }
            return
        }
        portRetryCount++
        if (portRetryCount == 1) {
            xposedModule.log(Log.INFO, HotspotAdbModule.TAG, "HotspotAdb: retrying fixed endpoint: $reason")
        }
        scheduleEvaluation(PORT_RETRY_DELAY_MS)
    }
}
