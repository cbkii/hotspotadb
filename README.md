<div align="center">
  <img src="screenshot.png" alt="Hotspot Wireless Debugging screen" width="420" />

# Hotspot Wireless Debugging

Use Android Wireless Debugging (ADB over Wi‑Fi with pairing/TLS) while your phone is the hotspot host.
</div>

## What this module does

Android normally expects the phone to be connected to Wi‑Fi as a client before Wireless Debugging can stay enabled.

This module changes that behavior so Wireless Debugging can stay available when your phone is running a hotspot (SoftAP). It preserves Android's native pairing, TLS and authorization model; it does not enable unauthenticated legacy `adb tcpip 5555`.

## Who this is for

- You tether other devices to your phone hotspot
- You want native Wireless Debugging (pair + connect), not plain `adb tcpip`
- You use a rooted phone with a modern libxposed-compatible framework

## Compatibility

- Android: **15 and 16 supported**
- Android 16 QPR1: dedicated `verifyWifiNetwork` compatibility path
- Module type: **libxposed API 101 module**
- Required scopes: `android` and `com.android.settings`
- Primary validation target: official Google Android 16 images on Pixel-class devices

ROMs can rename or remove private framework and Settings methods. The module probes known Android 15/16 variants independently and logs a structured hook-install summary instead of crashing when an optional path is absent.

## Requirements

- Rooted device
- Zygisk-enabled environment (Magisk or KernelSU setup)
- Compatible API 101 Xposed runtime, such as current LSPosed/Vector builds

## Install

1. Download the latest APK from [Releases](https://github.com/cbkii/hotspotadb/releases).
2. Install the APK.
3. Enable the module for both scopes:
   - `android`
   - `com.android.settings`
4. Reboot.

## Use the normal dynamic endpoint

1. Turn on hotspot.
2. Open hotspot settings or Developer options and enable Wireless Debugging.
3. Pair from the client:
   - `adb pair <host_ap_ip>:<pairing_port>`
4. Connect:
   - `adb connect <host_ap_ip>:<connect_port>`

Pairing and connection ports are separate. Automatic mDNS discovery may not work over a hotspot, so direct IP and port entry remains the reliable path.

## Optional fixed hotspot endpoint

Version 2.3.0 adds an opt-in **Fixed hotspot endpoint** switch inside the full Wireless Debugging screen.

When enabled and ready, the module exposes:

```text
192.168.49.1:5555
```

The implementation:

- adds `192.168.49.1/32` as a secondary address on the active hotspot interface;
- binds a bounded TCP byte proxy only to `192.168.49.1:5555`;
- forwards to adbd's current dynamic TLS listener on loopback;
- preserves native ADB pairing, TLS and authorization end to end;
- refuses to claim readiness if the alias conflicts, netd access fails, the fixed port is busy, Wireless Debugging is off, or the hotspot is inactive;
- removes the alias and stops the proxy when any prerequisite disappears.

The normal dynamic hotspot IP and port remain available and are used automatically whenever the fixed endpoint is disabled or unavailable. The feature does **not** switch adbd into legacy TCP mode.

## Host-to-client ADB over hotspot

You can also connect _from_ the Pixel host _to_ another Android device connected to the hotspot. The hotspotadb core module enables the host's own Wireless Debugging over hotspot, while host-to-client control additionally requires a local adb client on the host, such as Termux, and Wireless Debugging enabled on the target client device.

1. Connect the target Android device to the host's hotspot.
2. Enable Wireless Debugging on the target device.
3. From Termux on the hotspot host, pair and connect to the target device's own IP and ports.

See the [Host-to-Client ADB Architecture Note](docs/host-to-client-adb.md) and use `tools/hotspotadb-adb-netcheck.sh` for bounded IP, TCP and adb diagnostics.

## Troubleshooting

Check logs:

```bash
adb logcat -s HotspotAdb
```

The install summary should report which hooks were installed, skipped, missing or failed in `system_server` and `com.android.settings`.

For a useful bug report, include:

- device model and codename
- exact Android build and QPR level
- ROM/factory-image source
- root, Zygisk and Xposed runtime versions
- whether the dynamic or fixed endpoint was used
- relevant `HotspotAdb` logs

## Advanced technical notes

### Hook domains

1. **Settings process** (`com.android.settings`)
   - keeps the Wireless Debugging UI usable in hotspot mode;
   - shows the hotspot-side address;
   - injects the hotspot-screen Wireless Debugging entry;
   - injects the optional fixed-endpoint control and advertises it only when system_server marks it ready.
2. **Framework process** (`android` / `system_server`)
   - supplies synthetic hotspot connection information to ADB internals;
   - suppresses only framework network-change paths that would incorrectly tear Wireless Debugging down;
   - accepts the active hotspot at Android 16 QPR1's `verifyWifiNetwork` trust gate;
   - coordinates the optional subnet alias and TLS-preserving fixed-port proxy.

### Behavior details

- Trust identity uses a stable synthetic BSSID so hotspot MAC randomization does not reset trust every cycle.
- User-initiated Wireless Debugging disables are not intercepted.
- No broad `Settings.Global.putInt` hook is installed.
- Android-version-specific class names and hidden APIs are isolated in `compat/` adapters.
- Hotspot-interface selection is deterministic and excludes obvious cellular, VPN, tunnel and link-local candidates.

## Upstream monitoring

This standalone repo does not rely on GitHub fork-network status for sync awareness. `.github/workflows/upstream-release-monitor.yml` checks upstream releases on a schedule and opens or updates triage issues only when needed.

Suppression rules:

- tags or ranges in `.github/upstream-release-resolved-tags.txt` are skipped immediately;
- identical reruns are deduplicated by a deterministic issue marker;
- closed tracking issues are treated as resolved;
- empty or already-integrated release ranges are skipped;
- `--force` bypasses duplicate, resolved and integrated suppression for operator verification.

Manual run inputs include upstream repository/tag/base overrides, prerelease selection, force mode and dry-run verification. Every run emits stable metadata, a Markdown report, the upstream range patch and localized comparison artifacts.

## Build from source

Requires JDK 21 and Android SDK API 36.

```bash
./gradlew --no-daemon ktlintCheck detekt testDebugUnitTest assembleDebug
./scripts/validate-module.sh
```

Runtime behavior still requires exact-device validation after installing the APK, enabling both scopes and rebooting.

## Acknowledgements

This project started from the original work by **Dr. Serasprout** and contributors.

- Original upstream project: [droserasprout/io.drsr.hotspotadb](https://github.com/droserasprout/io.drsr.hotspotadb)
- Upstream contributors: [Contributors graph](https://github.com/droserasprout/io.drsr.hotspotadb/graphs/contributors)

Version 2.3.0 selectively ports the upstream 1.2.0 QPR1 compatibility architecture and optional fixed-endpoint feature while retaining this repository's modern libxposed API 101 lifecycle and safer teardown policy.

## License

[GPL-3.0](LICENSE)
