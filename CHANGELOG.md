# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.3.0] - 2026-07-12

### Added

- Android 16 QPR1 support through a dedicated modern libxposed API 101 `verifyWifiNetwork` hook that accepts the active hotspot without bypassing normal behavior when the hotspot is off.
- Optional fixed hotspot endpoint at `192.168.49.1:5555`, implemented as a conflict-checked `/32` SoftAP alias plus a bounded TLS-preserving byte proxy to adbd's current dynamic listener.
- Fixed-endpoint control in the full Wireless Debugging screen with separate requested/readiness state and automatic fallback to the dynamic hotspot endpoint.
- Centralized `compat/` adapters for ADB framework class locations, Settings class names, hidden SoftAP APIs, ADB binder access, system context lookup and netd class-name drift.
- JVM unit coverage for `ReflectionCompat` and hotspot-interface classification, now executed by CI.

### Changed

- Hotspot-interface discovery now scores candidates deterministically and excludes obvious cellular, VPN, tunnel, virtual, link-local, station-Wi-Fi and fixed-alias addresses from normal endpoint selection.
- Fixed-endpoint services stop and remove module-owned state whenever the hotspot, Wireless Debugging, dynamic adbd port or user preference becomes unavailable.
- Settings advertises the fixed endpoint only after system_server confirms both alias and proxy readiness.
- Version raised to `2.3.0` / `versionCode=13`.

### Security

- The fixed endpoint retains Android's native ADB pairing, TLS and authorization; it does not enable legacy unauthenticated `adb tcpip 5555`.
- The proxy binds only the fixed alias, limits concurrent clients, bounds loopback connection setup and closes active sockets during teardown.
- Upstream's broad `Settings.Global.putInt` interception was deliberately not ported because it could block intentional user disables.

## [2.2.3] - 2026-07-12

### Added

- Structured hook-install reporting for `system_server` and `com.android.settings`.
- Deterministic hotspot-interface scoring and clearer Settings endpoint wording.
- Host-to-client Termux diagnostics and architecture documentation.
- Deterministic upstream release monitoring with stable reports and failure artifacts.

### Fixed

- Consolidated Android 15/16 network-monitor callback handling and reduced repeated hotspot-state logging.
- Hardened upstream-monitor JSON parsing, issue identity, suppression and early-exit evidence generation.

## [2.1.8] - 2026-04-29

### Fixed

- `getCurrentWifiApInfo()` synthetic `AdbConnectionInfo` constructor selection is now tied to the hooked method return type, with compatibility checks before fallback class usage.
- Added explicit return-type and constructor-class logging so incompatible branch layouts fail soft with diagnosable logs instead of returning the wrong object type.

### Changed

- CI now explicitly installs `platform-tools`, `platforms;android-36`, and `build-tools;35.0.0` before Gradle tasks.
- Added `scripts/validate-module.sh` and wired it into CI to verify module metadata and guard against accidental broad `Settings.Global.putInt` interception.
- Version bumped to `2.1.8` / `versionCode=9`.

## [2.1.7] - 2026-04-29

### Fixed

- Corrected context-field literal escaping for reflective `this$0` lookup in framework handler and monitor context extraction.
- Added framework runtime decision logs for `getCurrentWifiApInfo()` original non-null/null branch selection before synthetic fallback.

### Changed

- Documentation wording now treats Android 16 monitor/receiver paths as branch candidates and source-backed expectations rather than unconditional stock-runtime confirmation.

## [2.1.6] - 2026-04-29

### Fixed

- Hardened Android 16 hotspot-only Wireless Debugging enablement path in both `SettingsHook` and `FrameworkHook` with deterministic class/method probing and stronger branch diagnostics.
- `AdbDebuggingHandler.getCurrentWifiApInfo()` compatibility path now logs context extraction and hotspot gating failures explicitly before synthetic `AdbConnectionInfo` creation.
- Teardown suppression probing now keeps named monitor/receiver hooks and anonymous `AdbDebuggingHandler$N` receiver fallback scans independent, so Android branch drift is easier to diagnose from logs.

### Changed

- Added centralized `ReflectionCompat` helpers for ordered class, method, constructor, and field probing with install-time signature logs.
- Improved hotspot/AP diagnostics in `HotspotHelper` including raw SoftAP state output and interface/IP rejection reasons when no AP IPv4 can be selected.

## [2.1.1] - 2026-04-12

### Changed

- Release 2.1.1.

## [2.1.0] - 2026-04-12

### Fixed

- **Critical: `AdbWifiNetworkMonitor` hook was not installed.** The previous implementation tried to cast `AdbWifiNetworkMonitor` as a `BroadcastReceiver` and silently skipped it. `AdbWifiNetworkMonitor` is a `ConnectivityManager.NetworkCallback` (confirmed Android 16 QPR2 AOSP). It is now hooked correctly via `onLost()` and `onCapabilitiesChanged()`.
- **Critical: removed `Settings.Global.putInt` fallback.** The previous last-resort fallback blocked any `adb_wifi_enabled=0` write while hotspot was active, including explicit user-initiated disables from Developer Options and the hotspot settings toggle. This was incorrect and dangerous. The fallback has been removed. The proper Android 16 hooks (`AdbWifiNetworkMonitor`, `AdbBroadcastReceiver`) now cover all realistic framework-driven disable paths.
- **`SettingsHook` listener leak: `ContentObserver` and `BroadcastReceiver` were never unregistered.** Added a `WifiTetherSettings.onStop` hook that unregisters the observer and receiver and cancels pending `Handler` callbacks. Re-registration on subsequent `onStart` calls is now correct.
- **`SettingsHook` re-registration after cleanup was blocked by early return.** The previous code returned early from `injectWirelessDebuggingPref` when the preference was already present in the screen (resuming fragment), skipping listener re-registration entirely after the `onStop` cleanup. The preference injection and listener registration are now separate; re-registration always runs unless listeners are already active.

### Changed

- `hookNetworkMonitorOrFallback` renamed to `hookNetworkMonitors`. Now installs hooks on **both** `AdbWifiNetworkMonitor` (NetworkCallback) and `AdbBroadcastReceiver` independently, because `AdbDebuggingManager` selects between them at runtime via `allowAdbWifiReconnect()` and both may be compiled into the image.
- `AdbWifiNetworkMonitor.onLost` and `onCapabilitiesChanged` receive `deoptimize()` calls to prevent JIT from bypassing the hooks in system_server.
- `getContextFromMonitor()` helper added for extracting `Context` from `AdbWifiNetworkMonitor` instances (tries `mContext` field, then an `AdbDebuggingManager` field, then `this$0`).
- Logging improved throughout: each hook now logs whether it was installed or skipped, which ADB monitor path was selected, and when a framework-driven disable is suppressed versus when a user-driven disable passes through.
- `HotspotHelper.getApInterfaceIp` now logs which interface and IP are selected and which are skipped as the station Wi-Fi IP.

### Removed

- `hookSettingsGlobalFallback` / `Settings.Global.putInt` intercept — replaced by correct Android 16 `AdbWifiNetworkMonitor` and `AdbBroadcastReceiver` hooks.
- `getContextFromResolver` helper — was only used by the removed fallback.

## [2.0.0] - 2026-04-12

### Changed

- **Migrated to modern libxposed API 101** — replaced legacy `de.robv.android.xposed:api:82` with `io.github.libxposed:api:101.0.1`. The module now requires an API 101-compatible framework.
- **Entry point**: replaced `assets/xposed_init` + `IXposedHookLoadPackage` with `META-INF/xposed/java_init.list` + `XposedModule`. Lifecycle now uses `onSystemServerStarting` and `onPackageLoaded`.
- **Manifest**: removed legacy Xposed metadata. Module name and description come from Android resources; scope and API data come from `META-INF/xposed/`.
- **Hook API**: all hooks migrated from `XC_MethodHook` to modern interceptor chains. `XposedHelpers` is no longer used.
- **SDK**: `compileSdk` and `targetSdk` raised to 36.

### Added

- Android 16 compatibility for top-level and nested `AdbConnectionInfo` layouts.
- `deoptimize()` on `getCurrentWifiApInfo` to prevent JIT inlining from bypassing the hook.
- Context extraction compatible with inner-class and top-level handler layouts.

### Removed

- `assets/xposed_init`, replaced by `META-INF/xposed/java_init.list`.
- Legacy scope resources, replaced by `META-INF/xposed/scope.list`.
- All imports of `de.robv.android.xposed.*`.

## [1.0.1] - 2026-04-10

### Fixed

- Fixed wrong IP shown on Wireless Debugging screen when hotspot is active.
- Fixed button label not updating on hotspot/Wi-Fi state changes.

## [1.0.0] - 2026-04-09

Initial release.

[2.3.0]: https://github.com/cbkii/hotspotadb/compare/2.2.3...2.3.0
[2.2.3]: https://github.com/cbkii/hotspotadb/compare/2.1.8...2.2.3
[2.1.8]: https://github.com/cbkii/hotspotadb/compare/2.1.7...2.1.8
[2.1.7]: https://github.com/cbkii/hotspotadb/compare/2.1.6...2.1.7
[2.1.6]: https://github.com/cbkii/hotspotadb/compare/2.1.1...2.1.6
[2.1.1]: https://github.com/cbkii/hotspotadb/compare/2.1.0...2.1.1
[2.1.0]: https://github.com/cbkii/hotspotadb/compare/2.0.0...2.1.0
[2.0.0]: https://github.com/cbkii/hotspotadb/compare/1.0.1...2.0.0
[1.0.1]: https://github.com/cbkii/hotspotadb/compare/1.0.0...1.0.1
[1.0.0]: https://github.com/cbkii/hotspotadb/releases/tag/1.0.0
