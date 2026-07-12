# Upstream 1.2.0 integration decision record

This document records how `droserasprout/io.drsr.hotspotadb` release `1.2.0` was evaluated and selectively integrated into `cbkii/hotspotadb` for release `2.3.0`.

## Architectural baseline

The repositories share ancestry but no longer use the same Xposed architecture:

| Area | `cbkii/hotspotadb` | upstream 1.2.0 |
| --- | --- | --- |
| Xposed API | modern libxposed API 101 | legacy XposedBridge API 82 |
| Entry point | `XposedModule` lifecycle | `IXposedHookLoadPackage` |
| Metadata | `META-INF/xposed/*` | legacy `assets/xposed_init` / manifest metadata |
| Android target | Android 15–16 | Android 13–16 QPR1 |
| Teardown policy | targeted monitor/receiver hooks | receiver hook plus broad global-setting fallback |
| Diagnostics | structured hook report | best-effort log messages |

A wholesale file replacement would have regressed the modern module lifecycle, metadata, diagnostics and user-disable behavior. The integration therefore ports behavior and compatibility knowledge, not legacy hook API code.

## Absorbed

### Android 16 QPR1 trust gate

Upstream identified `AdbDebuggingHandler.verifyWifiNetwork(String, String)` as an additional QPR1 enablement gate. The modern port installs an independent API 101 interceptor that returns `true` only while SoftAP is active and otherwise executes the original implementation.

### Compatibility adapters

Version-specific reflection knowledge is isolated in `compat/` components for:

- ADB framework class locations;
- Settings controller and fragment names;
- hidden SoftAP state, SSID and station-address APIs;
- ADB binder port lookup;
- system context lookup;
- netd AIDL class-name variants.

The hook policy remains separate from class-name and binder drift.

### Optional fixed endpoint

Upstream's fixed endpoint is retained as an opt-in feature, with additional safeguards:

- `192.168.49.1/32` is added only to the selected active SoftAP interface;
- an existing use of that address on another interface is treated as a conflict;
- the TCP proxy binds only the fixed alias rather than all interfaces;
- concurrent clients and loopback connection setup are bounded;
- the Settings UI advertises the fixed address only after alias and proxy readiness are confirmed;
- the proxy and module-owned alias are removed when any prerequisite disappears;
- the dynamic hotspot endpoint remains the fallback.

The proxy is an opaque byte pipe to adbd's native TLS listener. Pairing, authentication and encryption remain end to end.

### Settings lifecycle improvements

The fixed-endpoint control uses explicit start/stop lifecycle hooks and unregisters its observer. Existing hotspot-screen listener cleanup remains unchanged.

## Retained from the cbkii implementation

- Modern libxposed API 101 entry point and metadata.
- Independent `AdbWifiNetworkMonitor` and BroadcastReceiver teardown hooks.
- Return-type-compatible `AdbConnectionInfo` construction.
- Stable synthetic BSSID behavior.
- Structured hook-install reporting.
- Deterministic AP-interface scoring.
- No broad interception of user settings writes.
- Host-to-client diagnostic tooling and upstream-monitor infrastructure.

## Deliberately not absorbed

### Broad `Settings.Global.putInt` fallback

Upstream 1.2.0 falls back to intercepting `adb_wifi_enabled=0` when no receiver class is found. That cannot reliably distinguish framework teardown from an intentional user disable. The cbkii implementation continues to fail soft and log missing teardown hooks rather than override user intent.

### Legacy Xposed API 82 implementation

Legacy lifecycle, helper APIs and metadata were not restored. The port is expressed entirely through libxposed API 101.

### Minimum SDK 33

Upstream lowered `minSdk` to 33. The standalone cbkii module remains Android 15+ (`minSdk=35`) because its current private-API matrix, packaging and validation are scoped to Android 15/16. Expanding support requires separate Android 13/14 device evidence.

### Unconditional fixed-port advertising

Settings never displays `192.168.49.1:5555` merely because the user requested it. A separate readiness setting is written by system_server only after both network alias and proxy startup succeed.

## Validation boundary

Static validation covers formatting, detekt, JVM tests, APK assembly and modern Xposed packaging. Runtime acceptance still requires an exact-device pass after reboot:

1. verify hook summaries in `system_server` and `com.android.settings`;
2. enable Wireless Debugging during active hotspot operation;
3. verify Android 16 QPR1 does not flap the toggle through `verifyWifiNetwork`;
4. pair/connect through the dynamic endpoint;
5. enable the fixed endpoint and verify `192.168.49.1:5555` only appears when ready;
6. verify pairing/TLS still applies;
7. turn off Wireless Debugging and confirm user intent is not blocked;
8. turn off the hotspot and confirm the proxy and alias are removed.
