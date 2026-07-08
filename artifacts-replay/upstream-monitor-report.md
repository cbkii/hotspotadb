A new upstream release/change range was detected.

## Summary

- Upstream repo: droserasprout/io.drsr.hotspotadb
- Release range: 1.0.2...1.1.0
- Upstream compare URL: https://github.com/droserasprout/io.drsr.hotspotadb/compare/1.0.2...1.1.0
- Local branch: jules-3092906510404541140-18b592af
- Local commit: dbfd1095186bc9c47ea8dc9d3a44fadad6c5b72c
- Workflow run: https://github.com/cbkii/hotspotadb/actions/runs/local
- Force mode: False
- Fingerprint: c461d8b13271ada4259713f1be843dd8948a6304c4f79f35c27e0910efbb4ca8

## Upstream commit context

- [f7c99ce](https://github.com/droserasprout/io.drsr.hotspotadb/commit/f7c99ce0c38cbde67528bc7ea4970595c297d63b) Update README
- [015eac7](https://github.com/droserasprout/io.drsr.hotspotadb/commit/015eac74eb580a50ba5c6b15bc500eacd6c461b9) Fix ktlint: wrap multiline call on SubnetAlias.getNetd
- [f80753b](https://github.com/droserasprout/io.drsr.hotspotadb/commit/f80753bbf348905890b1f615c9a36719d1333e19) Update README
- [ffa6c37](https://github.com/droserasprout/io.drsr.hotspotadb/commit/ffa6c37e3180989cfbcb044395377d49b5bcabbd) Unregister observers/receiver when fragment view is destroyed
- [9038042](https://github.com/droserasprout/io.drsr.hotspotadb/commit/9038042771b2c8bee527385d405f253957579aa8) Consolidate adb helpers in HotspotHelper, drop dead acceptor field
- [5b6437a](https://github.com/droserasprout/io.drsr.hotspotadb/commit/5b6437a1180401ee76dff123edfadb02a4538e02) Fix Wireless Debugging screen sync: refresh IP row, hide Fixed IP pref when off, reflect hotspot state in hotspot-screen toggle
- [cc1192f](https://github.com/droserasprout/io.drsr.hotspotadb/commit/cc1192f410ca8a1fe10d1caf92b607ec45fa6346) Update readme and screenshots
- [2229281](https://github.com/droserasprout/io.drsr.hotspotadb/commit/22292815afc220e23c226e467f415de94d5610ad) Place Fixed IP/port toggle after IP address row
- [99ee752](https://github.com/droserasprout/io.drsr.hotspotadb/commit/99ee752d9ec5fa06749e67102e207d2fd364b97e) Trim CHANGELOG, expand Fixed IP/port section in README
- [36fa22f](https://github.com/droserasprout/io.drsr.hotspotadb/commit/36fa22ff5fb491371a5ac288adce5828d6863244) Add Fixed IP/port toggle (1.1.0)

## Changed upstream files

| Status | Upstream file | Local equivalent | Upstream latest | Upstream previous | Local file |
| --- | --- | --- | --- | --- | --- |
| modified | `CHANGELOG.md` | `CHANGELOG.md` | [link](https://github.com/droserasprout/io.drsr.hotspotadb/blob/1.1.0/CHANGELOG.md) | [link](https://github.com/droserasprout/io.drsr.hotspotadb/blob/1.0.2/CHANGELOG.md) | [link](https://github.com/cbkii/hotspotadb/blob/dbfd1095186bc9c47ea8dc9d3a44fadad6c5b72c/CHANGELOG.md) |
| modified | `README.md` | `README.md` | [link](https://github.com/droserasprout/io.drsr.hotspotadb/blob/1.1.0/README.md) | [link](https://github.com/droserasprout/io.drsr.hotspotadb/blob/1.0.2/README.md) | [link](https://github.com/cbkii/hotspotadb/blob/dbfd1095186bc9c47ea8dc9d3a44fadad6c5b72c/README.md) |
| modified | `app/build.gradle.kts` | `app/build.gradle.kts` | [link](https://github.com/droserasprout/io.drsr.hotspotadb/blob/1.1.0/app/build.gradle.kts) | [link](https://github.com/droserasprout/io.drsr.hotspotadb/blob/1.0.2/app/build.gradle.kts) | [link](https://github.com/cbkii/hotspotadb/blob/dbfd1095186bc9c47ea8dc9d3a44fadad6c5b72c/app/build.gradle.kts) |
| added | `app/src/main/kotlin/io/drsr/hotspotadb/AdbPortProxy.kt` | `app/src/main/kotlin/io/drsr/hotspotadb/AdbPortProxy.kt` | [link](https://github.com/droserasprout/io.drsr.hotspotadb/blob/1.1.0/app/src/main/kotlin/io/drsr/hotspotadb/AdbPortProxy.kt) | N/A | [link](https://github.com/cbkii/hotspotadb/blob/dbfd1095186bc9c47ea8dc9d3a44fadad6c5b72c/app/src/main/kotlin/io/drsr/hotspotadb/AdbPortProxy.kt) |
| modified | `app/src/main/kotlin/io/drsr/hotspotadb/FrameworkHook.kt` | `app/src/main/kotlin/io/drsr/hotspotadb/FrameworkHook.kt` | [link](https://github.com/droserasprout/io.drsr.hotspotadb/blob/1.1.0/app/src/main/kotlin/io/drsr/hotspotadb/FrameworkHook.kt) | [link](https://github.com/droserasprout/io.drsr.hotspotadb/blob/1.0.2/app/src/main/kotlin/io/drsr/hotspotadb/FrameworkHook.kt) | [link](https://github.com/cbkii/hotspotadb/blob/dbfd1095186bc9c47ea8dc9d3a44fadad6c5b72c/app/src/main/kotlin/io/drsr/hotspotadb/FrameworkHook.kt) |
| modified | `app/src/main/kotlin/io/drsr/hotspotadb/HotspotAdbModule.kt` | `app/src/main/kotlin/io/drsr/hotspotadb/HotspotAdbModule.kt` | [link](https://github.com/droserasprout/io.drsr.hotspotadb/blob/1.1.0/app/src/main/kotlin/io/drsr/hotspotadb/HotspotAdbModule.kt) | [link](https://github.com/droserasprout/io.drsr.hotspotadb/blob/1.0.2/app/src/main/kotlin/io/drsr/hotspotadb/HotspotAdbModule.kt) | [link](https://github.com/cbkii/hotspotadb/blob/dbfd1095186bc9c47ea8dc9d3a44fadad6c5b72c/app/src/main/kotlin/io/drsr/hotspotadb/HotspotAdbModule.kt) |
| modified | `app/src/main/kotlin/io/drsr/hotspotadb/HotspotHelper.kt` | `app/src/main/kotlin/io/drsr/hotspotadb/HotspotHelper.kt` | [link](https://github.com/droserasprout/io.drsr.hotspotadb/blob/1.1.0/app/src/main/kotlin/io/drsr/hotspotadb/HotspotHelper.kt) | [link](https://github.com/droserasprout/io.drsr.hotspotadb/blob/1.0.2/app/src/main/kotlin/io/drsr/hotspotadb/HotspotHelper.kt) | [link](https://github.com/cbkii/hotspotadb/blob/dbfd1095186bc9c47ea8dc9d3a44fadad6c5b72c/app/src/main/kotlin/io/drsr/hotspotadb/HotspotHelper.kt) |
| modified | `app/src/main/kotlin/io/drsr/hotspotadb/SettingsHook.kt` | `app/src/main/kotlin/io/drsr/hotspotadb/SettingsHook.kt` | [link](https://github.com/droserasprout/io.drsr.hotspotadb/blob/1.1.0/app/src/main/kotlin/io/drsr/hotspotadb/SettingsHook.kt) | [link](https://github.com/droserasprout/io.drsr.hotspotadb/blob/1.0.2/app/src/main/kotlin/io/drsr/hotspotadb/SettingsHook.kt) | [link](https://github.com/cbkii/hotspotadb/blob/dbfd1095186bc9c47ea8dc9d3a44fadad6c5b72c/app/src/main/kotlin/io/drsr/hotspotadb/SettingsHook.kt) |
| added | `app/src/main/kotlin/io/drsr/hotspotadb/SubnetAlias.kt` | `app/src/main/kotlin/io/drsr/hotspotadb/SubnetAlias.kt` | [link](https://github.com/droserasprout/io.drsr.hotspotadb/blob/1.1.0/app/src/main/kotlin/io/drsr/hotspotadb/SubnetAlias.kt) | N/A | [link](https://github.com/cbkii/hotspotadb/blob/dbfd1095186bc9c47ea8dc9d3a44fadad6c5b72c/app/src/main/kotlin/io/drsr/hotspotadb/SubnetAlias.kt) |
| renamed | `screen1.png` | `screen1.png` | [link](https://github.com/droserasprout/io.drsr.hotspotadb/blob/1.1.0/screen1.png) | [link](https://github.com/droserasprout/io.drsr.hotspotadb/blob/1.0.2/screenshot.png) | [link](https://github.com/cbkii/hotspotadb/blob/dbfd1095186bc9c47ea8dc9d3a44fadad6c5b72c/screen1.png) |
| added | `screen2.png` | `screen2.png` | [link](https://github.com/droserasprout/io.drsr.hotspotadb/blob/1.1.0/screen2.png) | N/A | [link](https://github.com/cbkii/hotspotadb/blob/dbfd1095186bc9c47ea8dc9d3a44fadad6c5b72c/screen2.png) |

## Upstream release-to-release diffstat

```text
 CHANGELOG.md                                       |  11 +
 README.md                                          |  34 ++-
 app/build.gradle.kts                               |   4 +-
 .../main/kotlin/io/drsr/hotspotadb/AdbPortProxy.kt | 136 +++++++++++
 .../kotlin/io/drsr/hotspotadb/FrameworkHook.kt     |  70 ++++++
 .../kotlin/io/drsr/hotspotadb/HotspotAdbModule.kt  |   1 +
 .../kotlin/io/drsr/hotspotadb/HotspotHelper.kt     |  59 ++++-
 .../main/kotlin/io/drsr/hotspotadb/SettingsHook.kt | 271 ++++++++++++++++++---
 .../main/kotlin/io/drsr/hotspotadb/SubnetAlias.kt  | 102 ++++++++
 screenshot.png => screen1.png                      | Bin
 screen2.png                                        | Bin 0 -> 70813 bytes
 11 files changed, 637 insertions(+), 51 deletions(-)

```

## Upstream release-to-release diff

```diff
diff --git a/CHANGELOG.md b/CHANGELOG.md
index ea712b2..a9c35e2 100644
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -5,6 +5,16 @@ All notable changes to this project will be documented in this file.
 The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
 and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

+## [1.1.0] - 2026-04-17
+
+### Added
+
+- Added "Fixed IP/port" toggle on the Wireless Debugging screen to listen on `192.168.49.1:5555`.
+
+### Fixed
+
+- Various UI sync and lifecycle issues on Settings screens.
+
 ## [1.0.2] - 2026-04-12

 ### Added
@@ -22,6 +32,7 @@ and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0

 Initial release.

+[1.1.0]: https://github.com/droserasprout/io.drsr.hotspotadb/compare/1.0.2...1.1.0
 [1.0.2]: https://github.com/droserasprout/io.drsr.hotspotadb/compare/1.0.1...1.0.2
 [1.0.1]: https://github.com/droserasprout/io.drsr.hotspotadb/compare/1.0.0...1.0.1
 [1.0.0]: https://github.com/droserasprout/io.drsr.hotspotadb/releases/tag/1.0.0
diff --git a/README.md b/README.md
index de8a65d..391fce8 100644
--- a/README.md
+++ b/README.md
@@ -1,10 +1,11 @@
-<img src="screenshot.png" align="right" width="220">
+<!-- markdownlint-disable MD033 MD041 -->
+<img src="screen1.png" alt="Hotspot settings screen" align="right" width="220">

 # Hotspot Wireless Debugging

-Xposed module that allows Wireless Debugging (ADB over Wi-Fi) to work over Wi-Fi Hotspot on Android 15/16.
+Xposed module that makes Wireless Debugging (ADB over Wi-Fi) work over Wi-Fi Hotspot on Android 15/16.

-Android 11+ only enables Wireless Debugging when the device is connected to Wi-Fi as a client. This module hooks the Settings app and system framework to bypass that restriction, so hotspot guests can connect via ADB.
+Android 11+ only enables Wireless Debugging when the device is connected to Wi-Fi as a client. This module removes that restriction so hotspot guests can connect via ADB.

 ## Requirements

@@ -19,14 +20,14 @@ Android 11+ only enables Wireless Debugging when the device is connected to Wi-F
 | enchilada | 15 | LineageOS 22.2 | Magisk 30.7 </br> NeoZygisk 2.3 | LSPosed 1.9.2 </br> Vector 2.0 |
 | tucana | 16 | LineageOS 23.2 | Magisk 30.7 | Vector 2.0 |

-If this module works (or not) on your device/ROM, please [open an issue](https://github.com/droserasprout/io.drsr.hotspotadb/issues) with details!
+If this module works (or not) on your device/ROM, please [open an issue](https://github.com/droserasprout/io.drsr.hotspotadb/issues).

 ## Installation

-Grab the latest APK from Xposed Module Repo, [GitHub Releases](https://github.com/droserasprout/io.drsr.hotspotadb/releases), or [build from source](#building-from-source).
+Grab the APK from Xposed Module Repo, [GitHub Releases](https://github.com/droserasprout/io.drsr.hotspotadb/releases), or [build from source](#building-from-source).

 1. Install the APK
-2. Enable the module in LSPosed for both scopes:
+2. Enable the module in LSPosed for two scopes:
    - `com.android.settings`
    - `android` (System Framework)
 3. Reboot
@@ -35,22 +36,35 @@ Grab the latest APK from Xposed Module Repo, [GitHub Releases](https://github.co

 1. Enable Wi-Fi Hotspot
 2. Use the Wireless Debugging toggle on the hotspot settings screen, or go to Developer Options > Wireless Debugging
-3. Pair your client device: `adb pair <ip>:<pairing_port> <pairing_code>`
+3. On the first connection, pair your client device: `adb pair <ip>:<pairing_port> <pairing_code>`
 4. Connect: `adb connect <ip>:<port>`

+### Fixed IP/port (optional)
+
+<img src="screen2.png" alt="Fixes IP/port setting" align="right" width="220">
+
+Flip **Fixed IP/port** to always listen on `192.168.49.1:5555`. Lets you script the command without needing mDNS in your `adb` build. Pairing still uses the ephemeral port shown on screen (one-time step).
+
+How it works:
+
+- `192.168.49.1/24` is aliased on the hotspot interface via netd (secondary address)
+- A TCP proxy in `system_server` listens on `:5555` and forwards to adbd's ephemeral TLS port (TLS is end-to-end, proxy is just a byte pipe)
+
+Trade-off: if your upstream network also uses `192.168.49.0/24`, leave this feature off to avoid routing collisions.
+
 ## Building from source

 Requires JDK 21 and Android SDK.

 ```shell
-make build     # build debug APK
+make build     # debug APK
 make install   # install via Gradle
-make clean     # clean build artifacts
+make clean
 ```

 ## Other solutions

-[Magisk-WiFiADB](https://github.com/mrh929/magisk-wifiadb) — Magisk module, enables legacy `adb tcpip` on boot. Simpler (just Magisk, any Android), but unencrypted and not hotspot-aware. This module hooks native Wireless Debugging (TLS, pairing) with Settings UI, but needs LSPosed and Android 15/16.
+[Magisk-WiFiADB](https://github.com/mrh929/magisk-wifiadb) — enables legacy `adb tcpip` on boot. Simpler (Magisk only, any Android), but unencrypted and not hotspot-aware.

 ## License

diff --git a/app/build.gradle.kts b/app/build.gradle.kts
index 578203a..3b87413 100644
--- a/app/build.gradle.kts
+++ b/app/build.gradle.kts
@@ -17,8 +17,8 @@ android {
         applicationId = "io.drsr.hotspotadb"
         minSdk = 35
         targetSdk = 36
-        versionCode = 3
-        versionName = "1.0.2"
+        versionCode = 4
+        versionName = "1.1.0"
     }

     signingConfigs {
diff --git a/app/src/main/kotlin/io/drsr/hotspotadb/AdbPortProxy.kt b/app/src/main/kotlin/io/drsr/hotspotadb/AdbPortProxy.kt
new file mode 100644
index 0000000..91625c5
--- /dev/null
+++ b/app/src/main/kotlin/io/drsr/hotspotadb/AdbPortProxy.kt
@@ -0,0 +1,136 @@
+package io.drsr.hotspotadb
+
+import de.robv.android.xposed.XposedBridge
+import java.io.IOException
+import java.net.BindException
+import java.net.InetSocketAddress
+import java.net.ServerSocket
+import java.net.Socket
+import java.util.concurrent.Executors
+
+/**
+ * TCP proxy running in system_server. Binds 0.0.0.0:FIXED_PORT and forwards
+ * bytes to adbd's TLS listener on 127.0.0.1:realPort. TLS is preserved end-to-end;
+ * this is just a byte pipe so clients can always use the advertised fixed port.
+ */
+object AdbPortProxy {
+    private val lock = Any()
+
+    @Volatile
+    private var serverSocket: ServerSocket? = null
+
+    @Volatile
+    private var boundToPort: Int = -1
+
+    private val executor =
+        Executors.newCachedThreadPool { r ->
+            Thread(r, "HotspotAdb-Proxy-pump").apply { isDaemon = true }
+        }
+
+    fun start(realPort: Int) {
+        if (realPort <= 0) return
+        if (realPort == HotspotHelper.FIXED_PORT) {
+            // adbd happens to bind the fixed port already; nothing to proxy.
+            stop()
+            return
+        }
+        synchronized(lock) {
+            if (serverSocket?.isBound == true && boundToPort == realPort) return
+            stopLocked()
+            try {
+                val ss = ServerSocket()
+                ss.reuseAddress = true
+                ss.bind(InetSocketAddress("0.0.0.0", HotspotHelper.FIXED_PORT), 50)
+                serverSocket = ss
+                boundToPort = realPort
+                Thread({ acceptLoop(ss, realPort) }, "HotspotAdb-Proxy-accept").apply {
+                    isDaemon = true
+                    start()
+                }
+                XposedBridge.log(
+                    "HotspotAdb: proxy listening on 0.0.0.0:${HotspotHelper.FIXED_PORT} -> 127.0.0.1:$realPort",
+                )
+            } catch (e: BindException) {
+                XposedBridge.log("HotspotAdb: proxy bind failed (port busy?): $e")
+                serverSocket = null
+                boundToPort = -1
+            } catch (e: Exception) {
+                XposedBridge.log("HotspotAdb: proxy start failed: $e")
+                serverSocket = null
+                boundToPort = -1
+            }
+        }
+    }
+
+    fun stop() {
+        synchronized(lock) { stopLocked() }
+    }
+
+    private fun stopLocked() {
+        val ss = serverSocket
+        serverSocket = null
+        boundToPort = -1
+        if (ss != null) {
+            try {
+                ss.close()
+                XposedBridge.log("HotspotAdb: proxy stopped")
+            } catch (_: IOException) {
+            }
+        }
+    }
+
+    private fun acceptLoop(
+        ss: ServerSocket,
+        realPort: Int,
+    ) {
+        while (!Thread.currentThread().isInterrupted && !ss.isClosed) {
+            val client =
+                try {
+                    ss.accept()
+                } catch (_: IOException) {
+                    break
+                }
+            executor.submit { handle(client, realPort) }
+        }
+    }
+
+    private fun handle(
+        client: Socket,
+        realPort: Int,
+    ) {
+        var upstream: Socket? = null
+        try {
+            client.tcpNoDelay = true
+            upstream = Socket("127.0.0.1", realPort)
+            upstream.tcpNoDelay = true
+            val up = upstream
+            val downTask =
+                executor.submit {
+                    try {
+                        client.getInputStream().copyTo(up.getOutputStream(), bufferSize = 16 * 1024)
+                    } catch (_: IOException) {
+                    } finally {
+                        closeQuietly(client)
+                        closeQuietly(up)
+                    }
+                }
+            try {
+                up.getInputStream().copyTo(client.getOutputStream(), bufferSize = 16 * 1024)
+            } catch (_: IOException) {
+            }
+            downTask.cancel(true)
+        } catch (e: IOException) {
+            XposedBridge.log("HotspotAdb: proxy handle failed: $e")
+        } finally {
+            closeQuietly(client)
+            closeQuietly(upstream)
+        }
+    }
+
+    private fun closeQuietly(s: Socket?) {
+        try {
+            s?.close()
+        } catch (_: I
... (diff truncated, see workflow artifacts or run reproduce commands)
```

## Equivalent-file comparison against local current codebase

### `CHANGELOG.md`
- Upstream latest: [link](https://github.com/droserasprout/io.drsr.hotspotadb/blob/1.1.0/CHANGELOG.md)
- Local equivalent: [link](https://github.com/cbkii/hotspotadb/blob/dbfd1095186bc9c47ea8dc9d3a44fadad6c5b72c/CHANGELOG.md)
- Status: differs

```diff
diff --git a/tmp/tmpy0vpeeno b/CHANGELOG.md
index a9c35e2..b4e8904 100644
--- a/tmp/tmpy0vpeeno
+++ b/CHANGELOG.md
@@ -2,24 +2,97 @@

 All notable changes to this project will be documented in this file.

-The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
-and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
+The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

-## [1.1.0] - 2026-04-17
+## [2.1.8] - 2026-04-29

-### Added
+### Fixed
+
+- `getCurrentWifiApInfo()` synthetic `AdbConnectionInfo` constructor selection is now tied to the hooked method return type, with compatibility checks before fallback class usage.
+- Added explicit return-type and constructor-class logging so incompatible branch layouts fail soft with diagnosable logs instead of returning the wrong object type.
+
+### Changed
+
+- CI now explicitly installs `platform-tools`, `platforms;android-36`, and `build-tools;35.0.0` before Gradle tasks.
+- Added `scripts/validate-module.sh` and wired it into CI to verify module metadata and guard against accidental broad `Settings.Global.putInt` interception.
+- Version bumped to `2.1.8` / `versionCode=9`.
+
+## [2.1.7] - 2026-04-29
+
+### Fixed

-- Added "Fixed IP/port" toggle on the Wireless Debugging screen to listen on `192.168.49.1:5555`.
+- Corrected context-field literal escaping for reflective `this$0` lookup in framework handler and monitor context extraction.
+- Added framework runtime decision logs for `getCurrentWifiApInfo()` original non-null/null branch selection before synthetic fallback.
+
+### Changed
+
+- Documentation wording now treats Android 16 monitor/receiver paths as branch candidates and source-backed expectations rather than unconditional stock-runtime confirmation.
+
+## [2.1.6] - 2026-04-29

 ### Fixed

-- Various UI sync and lifecycle issues on
... (truncated)
```

### `README.md`
- Upstream latest: [link](https://github.com/droserasprout/io.drsr.hotspotadb/blob/1.1.0/README.md)
- Local equivalent: [link](https://github.com/cbkii/hotspotadb/blob/dbfd1095186bc9c47ea8dc9d3a44fadad6c5b72c/README.md)
- Status: differs

```diff
diff --git a/tmp/tmpez51x0vm b/README.md
index 391fce8..d537427 100644
--- a/tmp/tmpez51x0vm
+++ b/README.md
@@ -1,70 +1,131 @@
-<!-- markdownlint-disable MD033 MD041 -->
-<img src="screen1.png" alt="Hotspot settings screen" align="right" width="220">
+<div align="center">
+  <img src="screenshot.png" alt="Hotspot Wireless Debugging screen" width="420" />

 # Hotspot Wireless Debugging

-Xposed module that makes Wireless Debugging (ADB over Wi-Fi) work over Wi-Fi Hotspot on Android 15/16.
+Use Android Wireless Debugging (ADB over Wi‑Fi with pairing/TLS) while your phone is the hotspot host.
+</div>

-Android 11+ only enables Wireless Debugging when the device is connected to Wi-Fi as a client. This module removes that restriction so hotspot guests can connect via ADB.
+## What this module does

-## Requirements
+Android normally expects the phone to be connected to Wi‑Fi as a client before Wireless Debugging can stay enabled.
+
+This module changes that behavior so Wireless Debugging can stay available when your phone is running a hotspot (SoftAP).
+
+## Who this is for

-- Android 15/16
-- Magisk or other Zygisk implementation
-- LSPosed/Vector
+- You tether other devices to your phone hotspot
+- You want native Wireless Debugging (pair + connect), not plain `adb tcpip`
+- You use a rooted phone with an Xposed-compatible framework

-### Tested configurations
+## Compatibility (current baseline)

-| Device | Android | ROM | Zygisk | Xposed |
-| --- | --- | --- | --- | -- |
-| enchilada | 15 | LineageOS 22.2 | Magisk 30.7 </br> NeoZygisk 2.3 | LSPosed 1.9.2 </br> Vector 2.0 |
-| tucana | 16 | LineageOS 23.2 | Magisk 30.7 | Vector 2.0 |
+- Android: **15 supported**
+- Android: **16 expected to work** (framework-side branch drift still possible)
+- Module type: **libxposed API 101 module**
+- Scopes required: `android` and `com.android.settings`

-If this module works (or not) on your device/ROM, please [open an issue](https://github.com/droserasprout/io.drsr.h
... (truncated)
```

### `app/build.gradle.kts`
- Upstream latest: [link](https://github.com/droserasprout/io.drsr.hotspotadb/blob/1.1.0/app/build.gradle.kts)
- Local equivalent: [link](https://github.com/cbkii/hotspotadb/blob/dbfd1095186bc9c47ea8dc9d3a44fadad6c5b72c/app/build.gradle.kts)
- Status: differs

```diff
diff --git a/tmp/tmpdq8i21ar b/app/build.gradle.kts
index 3b87413..41648dd 100644
--- a/tmp/tmpdq8i21ar
+++ b/app/build.gradle.kts
@@ -11,14 +11,17 @@ detekt {

 android {
     namespace = "io.drsr.hotspotadb"
+    // API 36 = Android 16
     compileSdk = 36
+    buildToolsVersion = "35.0.0"

     defaultConfig {
         applicationId = "io.drsr.hotspotadb"
+        // minSdk stays at 35 (Android 15): the module targets Android 15+ only
         minSdk = 35
         targetSdk = 36
-        versionCode = 4
-        versionName = "1.1.0"
+        versionCode = 11
+        versionName = "2.2.2"
     }

     signingConfigs {
@@ -45,9 +48,18 @@ android {
     kotlinOptions {
         jvmTarget = "21"
     }
+
+    // Merge META-INF/xposed/* from src/main/resources into the APK.
+    // Modern libxposed modules use these files instead of assets/xposed_init and manifest metadata.
+    packaging {
+        resources {
+            merges += "META-INF/xposed/*"
+        }
+    }
 }

 dependencies {
-    compileOnly("de.robv.android.xposed:api:82")
+    // Modern libxposed API 101 — replaces legacy de.robv.android.xposed:api:82
+    compileOnly("io.github.libxposed:api:101.0.1")
     compileOnly("androidx.preference:preference:1.2.1")
 }

```

### `app/src/main/kotlin/io/drsr/hotspotadb/AdbPortProxy.kt`
- Upstream latest: [link](https://github.com/droserasprout/io.drsr.hotspotadb/blob/1.1.0/app/src/main/kotlin/io/drsr/hotspotadb/AdbPortProxy.kt)
- Local equivalent: [link](https://github.com/cbkii/hotspotadb/blob/dbfd1095186bc9c47ea8dc9d3a44fadad6c5b72c/app/src/main/kotlin/io/drsr/hotspotadb/AdbPortProxy.kt)
- Status: missing

### `app/src/main/kotlin/io/drsr/hotspotadb/FrameworkHook.kt`
- Upstream latest: [link](https://github.com/droserasprout/io.drsr.hotspotadb/blob/1.1.0/app/src/main/kotlin/io/drsr/hotspotadb/FrameworkHook.kt)
- Local equivalent: [link](https://github.com/cbkii/hotspotadb/blob/dbfd1095186bc9c47ea8dc9d3a44fadad6c5b72c/app/src/main/kotlin/io/drsr/hotspotadb/FrameworkHook.kt)
- Status: differs

```diff
diff --git a/tmp/tmpry_i3seq b/app/src/main/kotlin/io/drsr/hotspotadb/FrameworkHook.kt
index 5999368..32e17ab 100644
--- a/tmp/tmpry_i3seq
+++ b/app/src/main/kotlin/io/drsr/hotspotadb/FrameworkHook.kt
@@ -3,269 +3,519 @@ package io.drsr.hotspotadb
 import android.content.BroadcastReceiver
 import android.content.Context
 import android.content.Intent
-import android.database.ContentObserver
-import android.net.Uri
 import android.net.wifi.WifiManager
-import android.os.Handler
-import android.os.Looper
-import android.provider.Settings
-import de.robv.android.xposed.XC_MethodHook
-import de.robv.android.xposed.XposedBridge
-import de.robv.android.xposed.XposedHelpers
-import de.robv.android.xposed.callbacks.XC_LoadPackage
+import android.util.Log
+import io.github.libxposed.api.XposedModule
+import java.lang.reflect.Constructor

+/**
+ * Hooks in system_server (android scope) that keep Wireless Debugging alive while a Wi-Fi
+ * hotspot is active.
+ *
+ * Hook point 1 — getCurrentWifiApInfo()
+ *   AdbDebuggingHandler.getCurrentWifiApInfo() returns null when no station Wi-Fi is connected,
+ *   which causes the framework to refuse to start wireless debugging.  When hotspot is active we
+ *   return a synthetic AdbConnectionInfo so the framework accepts the AP network.
+ *
+ * Hook point 2 — network monitor / receiver suppression
+ *
+ *   Android 16 (allowAdbWifiReconnect enabled, the default):
+ *     AdbWifiNetworkMonitor is a ConnectivityManager.NetworkCallback.  Its onLost() and
+ *     onCapabilitiesChanged() tear down wireless debugging when the device loses station Wi-Fi.
+ *     We suppress those callbacks while hotspot is active.
+ *     Candidate path on Android 16 branches: com.android.server.adb.AdbWifiNetworkMonitor.
+ *
+ *   Android 16 (allowAdbWifiReconnect disabled):
+ *     AdbBroadcastReceiver handles WIFI_STATE_CHANGED / NETWORK_STATE_CHANGED broadcasts.
+ *     Candidate path on Android 16 branches: com.android.server.adb.AdbBroadcastReceiver.
+
... (truncated)
```

### `app/src/main/kotlin/io/drsr/hotspotadb/HotspotAdbModule.kt`
- Upstream latest: [link](https://github.com/droserasprout/io.drsr.hotspotadb/blob/1.1.0/app/src/main/kotlin/io/drsr/hotspotadb/HotspotAdbModule.kt)
- Local equivalent: [link](https://github.com/cbkii/hotspotadb/blob/dbfd1095186bc9c47ea8dc9d3a44fadad6c5b72c/app/src/main/kotlin/io/drsr/hotspotadb/HotspotAdbModule.kt)
- Status: differs

```diff
diff --git a/tmp/tmpqb5ng9xy b/app/src/main/kotlin/io/drsr/hotspotadb/HotspotAdbModule.kt
index b8bbbc6..2ef0b0a 100644
--- a/tmp/tmpqb5ng9xy
+++ b/app/src/main/kotlin/io/drsr/hotspotadb/HotspotAdbModule.kt
@@ -1,21 +1,39 @@
 package io.drsr.hotspotadb

-import de.robv.android.xposed.IXposedHookLoadPackage
-import de.robv.android.xposed.XposedBridge
-import de.robv.android.xposed.callbacks.XC_LoadPackage
+import android.util.Log
+import io.github.libxposed.api.XposedModule
+import io.github.libxposed.api.XposedModuleInterface.ModuleLoadedParam
+import io.github.libxposed.api.XposedModuleInterface.PackageLoadedParam
+import io.github.libxposed.api.XposedModuleInterface.SystemServerStartingParam

-class HotspotAdbModule : IXposedHookLoadPackage {
-    override fun handleLoadPackage(lpparam: XC_LoadPackage.LoadPackageParam) {
-        XposedBridge.log("HotspotAdb: handleLoadPackage ${lpparam.packageName} / ${lpparam.processName}")
-        when (lpparam.packageName) {
-            "com.android.settings" -> {
-                XposedBridge.log("HotspotAdb: hooking Settings")
-                SettingsHook.init(lpparam)
-            }
-            "android" -> {
-                XposedBridge.log("HotspotAdb: hooking framework")
-                FrameworkHook.init(lpparam)
-            }
+/**
+ * Modern libxposed API 101 entry point.
+ *
+ * Lifecycle:
+ *  - onModuleLoaded    : called once per process load; log framework info.
+ *  - onSystemServerStarting : called in system_server; install framework (ADB) hooks.
+ *  - onPackageLoaded   : called when an app package's classloader is ready;
+ *                        install Settings UI hooks for com.android.settings.
+ */
+class HotspotAdbModule : XposedModule() {
+    companion object {
+        const val TAG = "HotspotAdb"
+    }
+
+    override fun onModuleLoaded(param: ModuleLoadedParam) {
+        log(Log.INFO, TAG, "module loaded in ${param.processName}")
+        log(Log.INFO, TAG, "framework: $frameworkName $fram
... (truncated)
```

### `app/src/main/kotlin/io/drsr/hotspotadb/HotspotHelper.kt`
- Upstream latest: [link](https://github.com/droserasprout/io.drsr.hotspotadb/blob/1.1.0/app/src/main/kotlin/io/drsr/hotspotadb/HotspotHelper.kt)
- Local equivalent: [link](https://github.com/cbkii/hotspotadb/blob/dbfd1095186bc9c47ea8dc9d3a44fadad6c5b72c/app/src/main/kotlin/io/drsr/hotspotadb/HotspotHelper.kt)
- Status: differs

```diff
diff --git a/tmp/tmpocx8oi6h b/app/src/main/kotlin/io/drsr/hotspotadb/HotspotHelper.kt
index 7cf1209..f07dd4a 100644
--- a/tmp/tmpocx8oi6h
+++ b/app/src/main/kotlin/io/drsr/hotspotadb/HotspotHelper.kt
@@ -2,56 +2,57 @@ package io.drsr.hotspotadb

 import android.content.Context
 import android.net.wifi.WifiManager
-import android.provider.Settings
-import de.robv.android.xposed.XposedBridge
+import android.util.Log
 import java.net.Inet4Address
 import java.net.NetworkInterface

 object HotspotHelper {
-    const val FIXED_ENDPOINT_KEY = "hotspot_adb_fixed_endpoint"
-    const val ADB_WIFI_ENABLED = "adb_wifi_enabled"
-    const val FIXED_IP = "192.168.49.1"
-    const val FIXED_PORT = 5555
+    private const val TAG = HotspotAdbModule.TAG

+    /**
+     * Hidden Android constant for WifiManager.WIFI_AP_STATE_ENABLED.
+     * Reflection is used because this is not in the public SDK but is stable across AOSP branches.
+     */
     private const val WIFI_AP_STATE_ENABLED = 13
-
-    fun isFixedEndpointEnabled(context: Context): Boolean {
-        return Settings.Global.getInt(context.contentResolver, FIXED_ENDPOINT_KEY, 0) == 1
-    }
-
-    fun isAdbWifiEnabled(context: Context): Boolean {
-        return Settings.Global.getInt(context.contentResolver, ADB_WIFI_ENABLED, 0) == 1
-    }
-
-    /** Returns adbd's current wireless TLS port, or -1 if unavailable. */
-    fun getAdbWirelessPort(): Int {
-        return try {
-            val serviceManagerClass = Class.forName("android.os.ServiceManager")
-            val binder =
-                serviceManagerClass.getMethod("getService", String::class.java)
-                    .invoke(null, "adb")
-            val iAdbManagerStub = Class.forName("android.debug.IAdbManager\$Stub")
-            val adbService =
-                iAdbManagerStub.getMethod("asInterface", android.os.IBinder::class.java)
-                    .invoke(null, binder)
-            adbService.javaClass.getMethod("getAdbWirelessPort").invoke(ad
... (truncated)
```

### `app/src/main/kotlin/io/drsr/hotspotadb/SettingsHook.kt`
- Upstream latest: [link](https://github.com/droserasprout/io.drsr.hotspotadb/blob/1.1.0/app/src/main/kotlin/io/drsr/hotspotadb/SettingsHook.kt)
- Local equivalent: [link](https://github.com/cbkii/hotspotadb/blob/dbfd1095186bc9c47ea8dc9d3a44fadad6c5b72c/app/src/main/kotlin/io/drsr/hotspotadb/SettingsHook.kt)
- Status: differs

```diff
diff --git a/tmp/tmpt23tgot3 b/app/src/main/kotlin/io/drsr/hotspotadb/SettingsHook.kt
index e5a2d4e..411484b 100644
--- a/tmp/tmpt23tgot3
+++ b/app/src/main/kotlin/io/drsr/hotspotadb/SettingsHook.kt
@@ -10,302 +10,419 @@ import android.net.wifi.WifiManager
 import android.os.Handler
 import android.os.Looper
 import android.provider.Settings
-import de.robv.android.xposed.XC_MethodHook
-import de.robv.android.xposed.XposedBridge
-import de.robv.android.xposed.XposedHelpers
-import de.robv.android.xposed.callbacks.XC_LoadPackage
+import android.util.Log
+import io.github.libxposed.api.XposedModule
+import java.lang.reflect.Method
+import java.util.Collections
+import java.util.WeakHashMap

+/**
+ * Hooks inside the com.android.settings process.
+ *
+ * Three hooks:
+ *
+ * 1. WirelessDebuggingPreferenceController.isWifiConnected(Context)
+ *    Returns true when hotspot is active so the Wireless Debugging UI stays usable.
+ *
+ * 2. AdbIpAddressPreferenceController.getIpv4Address()
+ *    Returns the hotspot AP interface IP instead of the station Wi-Fi IP when hotspot is active.
+ *
+ * 3. WifiTetherSettings.onStart() / onStop()
+ *    onStart: injects a "Wireless debugging" toggle into the hotspot settings screen and
+ *             registers a ContentObserver + BroadcastReceiver to keep it in sync.
+ *    onStop:  unregisters the ContentObserver and BroadcastReceiver, cancels pending handler
+ *             callbacks.  Prevents leaks across navigation in/out of the hotspot settings screen.
+ *
+ * Lifecycle safety
+ * - The preference injection and listener registration are separate concerns.
+ * - When the fragment resumes after onStop (clean state), the preference is retrieved from the
+ *   existing PreferenceScreen and listeners are re-registered.
+ * - The fragmentExtras WeakHashMap holds state keyed on fragment instances; entries are eligible
+ *   for GC when the fragment is destroyed.
+ *
+ * No XposedHelpers in modern API — all reflection uses java.lang.r
... (truncated)
```

### `app/src/main/kotlin/io/drsr/hotspotadb/SubnetAlias.kt`
- Upstream latest: [link](https://github.com/droserasprout/io.drsr.hotspotadb/blob/1.1.0/app/src/main/kotlin/io/drsr/hotspotadb/SubnetAlias.kt)
- Local equivalent: [link](https://github.com/cbkii/hotspotadb/blob/dbfd1095186bc9c47ea8dc9d3a44fadad6c5b72c/app/src/main/kotlin/io/drsr/hotspotadb/SubnetAlias.kt)
- Status: missing

### `screen1.png`
- Upstream latest: [link](https://github.com/droserasprout/io.drsr.hotspotadb/blob/1.1.0/screen1.png)
- Local equivalent: [link](https://github.com/cbkii/hotspotadb/blob/dbfd1095186bc9c47ea8dc9d3a44fadad6c5b72c/screen1.png)
- Status: missing

### `screen2.png`
- Upstream latest: [link](https://github.com/droserasprout/io.drsr.hotspotadb/blob/1.1.0/screen2.png)
- Local equivalent: [link](https://github.com/cbkii/hotspotadb/blob/dbfd1095186bc9c47ea8dc9d3a44fadad6c5b72c/screen2.png)
- Status: missing

## Reproduce locally

```bash
git clone https://github.com/cbkii/hotspotadb.git
cd hotspotadb
git remote add upstream https://github.com/droserasprout/io.drsr.hotspotadb.git
git fetch upstream --tags
git diff 1.0.2 1.1.0
```

## Checklist

- [ ] Review release notes
- [ ] Inspect changed upstream files
- [ ] Compare equivalent local files
- [ ] Decide which changes to port
- [ ] Add resolved tag/range to `.github/upstream-release-resolved-tags.txt`
- [ ] Close this issue when triage is complete

<!-- upstream-monitor:fingerprint:c461d8b13271ada4259713f1be843dd8948a6304c4f79f35c27e0910efbb4ca8 -->