<div align="center">
  <img src="screenshot.png" alt="Hotspot Wireless Debugging screen" width="420" />

# Hotspot Wireless Debugging

Use Android Wireless Debugging (ADB over Wi‑Fi with pairing/TLS) while your phone is the hotspot host.
</div>

## What this module does

Android normally expects the phone to be connected to Wi‑Fi as a client before Wireless Debugging can stay enabled.

This module changes that behavior so Wireless Debugging can stay available when your phone is running a hotspot (SoftAP).

## Who this is for

- You tether other devices to your phone hotspot
- You want native Wireless Debugging (pair + connect), not plain `adb tcpip`
- You use a rooted phone with an Xposed-compatible framework

## Compatibility (current baseline)

- Android: **15 supported**
- Android: **16 expected to work** (framework-side branch drift still possible)
- Module type: **libxposed API 101 module**
- Scopes required: `android` and `com.android.settings`

## Requirements

- Rooted device
- Zygisk-enabled environment (Magisk or KernelSU setup)
- Compatible Xposed runtime

## Install

1. Download the latest APK from [Releases](https://github.com/cbkii/hotspotadb/releases).
2. Install the APK.
3. Enable the module for both scopes:
   - `android`
   - `com.android.settings`
4. Reboot.

## Use

1. Turn on hotspot.
2. Open hotspot settings or Developer options and enable Wireless Debugging.
3. Pair from client:
   - `adb pair <ip>:<pairing_port> <pairing_code>`
4. Connect:
   - `adb connect <ip>:<port>`

## Host-to-client ADB over hotspot

You can also connect _from_ the Pixel host _to_ another Android device connected to the hotspot. The hotspotadb core module enables the host's own Wireless Debugging over hotspot, while host-to-client control additionally requires a local adb client on the host (like Termux) and Wireless Debugging enabled on the target client device.

1. Ensure the target client device is connected to the Pixel host's hotspot.
2. Enable Wireless Debugging on the target client device.
3. Use Termux on the Pixel host to pair and connect to the client device's IP and port (e.g., `adb pair <client_ip>:<pairing_port>` and `adb connect <client_ip>:<port>`). Note: automatic discovery may not work over hotspots; direct IP:port is required.

See the [Host-to-Client ADB Architecture Note](docs/host-to-client-adb.md) for full details, and use the included diagnostic script `tools/hotspotadb-adb-netcheck.sh` if you need help finding IPs or checking adb readiness.

## Troubleshooting (quick)

Check logs:

```bash
adb logcat -s HotspotAdb
```

If it fails, include these in your bug report:

- device model
- Android version
- ROM
- root + framework versions
- relevant `HotspotAdb` logs

## Advanced technical notes

### Hook domains

1. **Settings process** (`com.android.settings`)
   - keeps UI enabled in hotspot mode
   - shows hotspot-side IP for ADB
   - injects hotspot settings entry behavior
2. **Framework process** (`android` / `system_server`)
   - supplies hotspot connection info to ADB internals
   - blocks framework network-change paths that otherwise disable hotspot wireless debugging

### Behavior details

- Trust identity uses a synthetic stable BSSID to avoid trust reset on each hotspot cycle.
- Hotspot detection and IP discovery are heuristic by design.

## Upstream monitoring

`.github/workflows/upstream-release-monitor.yml` checks the configured upstream at 05:25 UTC each day and can also be run manually. It resolves an exact release identity, compares one coherent Git range, and creates or updates one canonical tracking issue only when triage is needed.

Automatic stable mode uses GitHub's latest stable release and its immediately preceding eligible stable release. With prereleases enabled, stable and prerelease entries follow the GitHub releases API order. Drafts are always excluded. A genuine first release is compared with Git's empty tree; an explicitly or automatically selected base that cannot be fetched is an error rather than a silent downgrade.

Suppression is deterministic:

- exact tags/ranges in `.github/upstream-release-resolved-tags.txt` are skipped before Git comparison work;
- an empty upstream delta returns `skipped_no_changes`;
- a delta whose mapped local states are all already identical/absent returns `skipped_integrated`;
- a closed canonical tracking issue returns `skipped_closed` and stays closed;
- an unchanged open issue fingerprint returns `skipped_duplicate`;
- `force` bypasses resolved, integrated, closed and duplicate suppression, but never validation, API, Git or mutation errors.

Manual inputs under **Actions > Upstream Release Monitor**:

- `upstream_repo`: override the default `droserasprout/io.drsr.hotspotadb` repository;
- `upstream_tag`: use an exact head tag/ref;
- `upstream_base_tag`: use an exact base tag/ref;
- `include_prerelease`: include prereleases in automatic selection;
- `force`: bypass normal suppression for an operator-requested update/reopen;
- `dry_run`: generate the complete report and artifacts without reading or mutating tracking issues.

Every result writes a stable evidence package: `metadata.json`, `upstream-monitor-report.md`, `upstream-release.diff`, `step-summary.md`, warnings/errors files, and bounded per-file comparison artifacts where applicable. The metadata records requested/resolved tags, effective refs/commits, comparison mode, result, issue action/number/URL, and diagnostics.

Resolved-tag entries use strict literal grammar:

```text
<tag>
<owner/repo>@<tag>
<base>..<head>
<owner/repo>@<base>..<head>
```

Bare entries apply only to the default upstream; an overridden upstream requires the tuple form. Malformed entries fail the run rather than being ignored.

## Build from source

Requires JDK 21 and Android SDK API 36.

```bash
./gradlew ktlintCheck detekt assembleDebug
```

## Acknowledgements

This project started from the original work by **Dr. Serasprout** and contributors.

- Original upstream project: [droserasprout/io.drsr.hotspotadb](https://github.com/droserasprout/io.drsr.hotspotadb)
- Upstream contributors: [Contributors graph](https://github.com/droserasprout/io.drsr.hotspotadb/graphs/contributors)

Thank you to the upstream maintainers and contributors for the foundation this standalone repository builds on.

## License

[GPL-3.0](LICENSE)
