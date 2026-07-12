package io.drsr.hotspotadb

import android.util.Log
import io.github.libxposed.api.XposedModule
import java.io.IOException
import java.net.BindException
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.net.Socket
import java.util.Collections
import java.util.concurrent.Executors
import java.util.concurrent.Semaphore

/**
 * Bounded TCP byte proxy from the optional fixed hotspot address to adbd's dynamic TLS port.
 * Pairing and authentication remain end-to-end between adb and adbd; this layer never parses TLS.
 */
object AdbPortProxy {
    private const val CONNECT_TIMEOUT_MS = 5_000
    private const val MAX_CLIENTS = 4

    private val lock = Any()
    private val clientPermits = Semaphore(MAX_CLIENTS)
    private val activeSockets = Collections.synchronizedSet(mutableSetOf<Socket>())
    private val executor =
        Executors.newCachedThreadPool { runnable ->
            Thread(runnable, "HotspotAdb-Proxy").apply { isDaemon = true }
        }

    @Volatile
    private var serverSocket: ServerSocket? = null

    @Volatile
    private var upstreamPort: Int = -1

    fun start(
        realPort: Int,
        module: XposedModule,
    ): Boolean {
        if (realPort <= 0) return false
        if (realPort == HotspotHelper.FIXED_PORT) {
            stop(module)
            return true
        }

        synchronized(lock) {
            if (serverSocket?.isBound == true && upstreamPort == realPort) return true
            stopLocked(module)
            return try {
                val server = ServerSocket()
                server.reuseAddress = true
                val bindAddress = InetAddress.getByName(HotspotHelper.FIXED_IP)
                server.bind(InetSocketAddress(bindAddress, HotspotHelper.FIXED_PORT), MAX_CLIENTS)
                serverSocket = server
                upstreamPort = realPort
                Thread(
                    { acceptLoop(server, realPort, module) },
                    "HotspotAdb-ProxyAccept",
                ).apply {
                    isDaemon = true
                    start()
                }
                module.log(
                    Log.INFO,
                    HotspotAdbModule.TAG,
                    "HotspotAdb: fixed proxy ${HotspotHelper.FIXED_IP}:${HotspotHelper.FIXED_PORT} " +
                        "-> 127.0.0.1:$realPort",
                )
                true
            } catch (e: BindException) {
                module.log(Log.ERROR, HotspotAdbModule.TAG, "HotspotAdb: fixed proxy port unavailable: $e")
                serverSocket = null
                upstreamPort = -1
                false
            } catch (e: IOException) {
                module.log(Log.ERROR, HotspotAdbModule.TAG, "HotspotAdb: fixed proxy start failed: $e")
                serverSocket = null
                upstreamPort = -1
                false
            }
        }
    }

    fun stop(module: XposedModule) {
        synchronized(lock) { stopLocked(module) }
    }

    private fun stopLocked(module: XposedModule) {
        val server = serverSocket
        val wasActive = server != null || activeSockets.isNotEmpty()
        serverSocket = null
        upstreamPort = -1
        closeQuietly(server)
        synchronized(activeSockets) {
            activeSockets.toList().forEach(::closeQuietly)
            activeSockets.clear()
        }
        if (wasActive) {
            module.log(Log.INFO, HotspotAdbModule.TAG, "HotspotAdb: fixed proxy stopped")
        }
    }

    private fun acceptLoop(
        server: ServerSocket,
        realPort: Int,
        module: XposedModule,
    ) {
        while (!server.isClosed && !Thread.currentThread().isInterrupted) {
            val client =
                try {
                    server.accept()
                } catch (_: IOException) {
                    break
                }
            if (!clientPermits.tryAcquire()) {
                module.log(Log.WARN, HotspotAdbModule.TAG, "HotspotAdb: fixed proxy client limit reached")
                closeQuietly(client)
                continue
            }
            executor.execute {
                try {
                    handle(client, realPort, module)
                } finally {
                    clientPermits.release()
                }
            }
        }
    }

    private fun handle(
        client: Socket,
        realPort: Int,
        module: XposedModule,
    ) {
        var upstream: Socket? = null
        activeSockets += client
        try {
            client.tcpNoDelay = true
            upstream = Socket()
            upstream.connect(InetSocketAddress(InetAddress.getLoopbackAddress(), realPort), CONNECT_TIMEOUT_MS)
            upstream.tcpNoDelay = true
            activeSockets += upstream

            val connectedUpstream = upstream
            val upload =
                executor.submit {
                    try {
                        client.getInputStream().copyTo(connectedUpstream.getOutputStream(), 16 * 1024)
                    } catch (_: IOException) {
                    } finally {
                        closeQuietly(client)
                        closeQuietly(connectedUpstream)
                    }
                }
            try {
                connectedUpstream.getInputStream().copyTo(client.getOutputStream(), 16 * 1024)
            } catch (_: IOException) {
            } finally {
                upload.cancel(true)
            }
        } catch (e: IOException) {
            module.log(Log.WARN, HotspotAdbModule.TAG, "HotspotAdb: fixed proxy connection failed: $e")
        } finally {
            activeSockets -= client
            upstream?.let { activeSockets -= it }
            closeQuietly(client)
            closeQuietly(upstream)
        }
    }

    private fun closeQuietly(socket: Socket?) {
        try {
            socket?.close()
        } catch (_: IOException) {
        }
    }

    private fun closeQuietly(server: ServerSocket?) {
        try {
            server?.close()
        } catch (_: IOException) {
        }
    }
}
