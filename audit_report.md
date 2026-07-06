# hotspotadb Android 16 / Xposed API 101 Audit

## Executive verdict
- **Is the app likely to meet its goal on Pixel 9a Android 16?**
Yes. The app properly targets Android 16 / API 36 with API 101 libxposed modules, and hooks the necessary system paths based on currently understood Android 16 internals, handling both `AdbWifiNetworkMonitor` and `AdbBroadcastReceiver` path variations via reflective fallback.
- **What are the top 3 reliability risks?**
  1. **Android 16 framework/Settings drift**: Changes to `AdbWifiNetworkMonitor`, `AdbConnectionInfo` constructor, or Settings fragment paths might break hooks if AOSP changes them before Android 16 stable.
  2. **Hotspot IP discovery heuristics**: If the Pixel 9a uses a different interface naming convention for softAP or a new tethering setup, `HotspotHelper.getHotspotIpAddress` might fail to locate it.
  3. **Hook Exceptions and crashes**: If `ReflectionCompat` encounters unhandled states or AOSP changes internal representations wildly, it could theoretically crash components within `system_server` or `com.android.settings`.

## Confirmed current architecture
- **Build/API/scopes**: Targeting `compileSdk 36`, `targetSdk 36`, `minSdk 35`. Uses libxposed API 101.0.1. Correctly configures `module.prop`, `scope.list`, and `java_init.list`. Scope is correctly set to `android` and `com.android.settings`.
- **Framework hooks**: Hooks `AdbDebuggingHandler.getCurrentWifiApInfo()`, providing synthetic `AdbConnectionInfo` based on hotspot status. Hooks `AdbWifiNetworkMonitor.onLost`/`onCapabilitiesChanged` or `AdbBroadcastReceiver` to safely suppress teardown when a hotspot is active.
- **Settings hooks**: Overrides `WirelessDebuggingPreferenceController.isWifiConnected` to keep UI available. Adjusts IP address via `AdbIpAddressPreferenceController.getIpv4Address`. Modifies `WifiTetherSettings` (and `AdbWirelessDebuggingPreferenceController` Android 16 paths) to inject a UI switch safely.
- **Diagnostic script**: A bash script (`tools/hotspotadb-adb-netcheck.sh`) to check local network parameters and perform test adb connections. Safely uses bounded commands via `timeout` helper function and does not log pairing codes.
- **Docs**: `docs/host-to-client-adb.md` clearly outlines Direction A vs Direction B limitations and requirements, correctly distinguishing host AP IP vs target client IP, and noting mDNS limitations over hotspot interfaces.

## Findings Implemented in this PR

1. **Structured Runtime Hook Reporting**: Added `HookReporter` to track and summarize the installation status of hooks in both `system_server` and `com.android.settings`. This significantly improves observability without spamming logs on hot paths.
2. **FrameworkHook Callback Hardening**: Refactored `AdbWifiNetworkMonitor` callback handling to use a shared interceptor helper, removing duplicated logic, safely handling context extraction, and ensuring failures pass-through without crashing.
3. **HotspotHelper AP IP Selection**: Implemented a deterministic `InterfaceCandidate` scoring approach (e.g. prioritizing `ap*`, `swlan*`, `softap*`) to select the best AP interface, while properly excluding loopback, down, VPN, and station IPs. Reduced log spam for repeated `isHotspotActive` state checks by logging only on state changes.
4. **Settings UI Wording Improvement**: Updated the summary injected into Settings to say "Host AP IP" instead of "Host IP" for clarity between the host and client devices.
5. **Diagnostic Script Refinement**: Updated `tools/hotspotadb-adb-netcheck.sh` per review feedback to use Bash-native substring extraction (`read`) and substring matching (`[[ ... == *...* ]]`) instead of `printf` and `grep`, while keeping formatting on a single line.

## Recommended implementation order
1. **Must-fix before release**: Verification on a real Pixel 9a Android 16 device to ensure internal Android 16 symbols have not drifted since the current codebase assumptions.
2. **Should-fix for reliability**: Ensure the scoring heuristics in `HotspotHelper` adequately capture Pixel 9a tethering interface names in the wild.
3. **Explicit non-goals**: Migrating to libxposed API 102. Implementing persistent, unauthenticated `adb tcpip 5555`.

## Validation commands run
- **Command**: `timeout 120 ./gradlew ktlintCheck detekt assembleDebug`
- **Result**: Passed (ktlint, detekt, and assembleDebug completed successfully).
- **Command**: `timeout 10 bash -n tools/hotspotadb-adb-netcheck.sh`
- **Result**: Passed (no syntax errors).
- **Command**: `timeout 10 shellcheck tools/hotspotadb-adb-netcheck.sh`
- **Result**: Skipped (shellcheck not available in current environment).
- **Command**: `timeout 20 ./scripts/validate-module.sh`
- **Result**: Passed (Module validation passed).

## Remaining limitations and Open questions
1. **Real Device Validation**: The runtime hooks and AP interface selection improvements in this PR still require validation against a real Pixel 9a device running an Android 16 preview/stable build to confirm that hook targeting matches actual firmware internals.
2. **AOSP/Pixel internals verification**: Need to observe the actual `AdbWifiNetworkMonitor` behavior and Settings controller usage on a live Android 16 device.
3. **Scope and Assumptions**: API target has explicitly been kept at 101, and no new scopes have been added, adhering to instructions and avoiding speculative features.