# AGENTS.md

## Project identity

This repository is an Android Xposed/LSPosed module that enables native Wireless Debugging (ADB over Wi‑Fi / TLS pairing) to work when the device is acting as a Wi‑Fi hotspot, not only when it is a Wi‑Fi client.

Today, the codebase is a **legacy XposedBridge module**:
- dependency: `de.robv.android.xposed:api:82`
- entrypoint: `assets/xposed_init`
- manifest metadata: `xposedmodule`, `xposedminversion`, `xposedscope`
- scopes: `android` and `com.android.settings`

Do **not** describe or treat the current code as a modern libxposed / API 101 module unless the task is explicitly a migration.

## What matters most in this repo

The module has two hook domains and both must stay coherent:

1. **Settings process hooks** (`com.android.settings`)
   - `WirelessDebuggingPreferenceController.isWifiConnected(...)`
   - `AdbIpAddressPreferenceController.getIpv4Address()`
   - `WifiTetherSettings.onStart()` and injected preference behaviour

2. **Framework / system_server hooks** (`android` scope)
   - ADB Wi‑Fi / wireless debugging internals in `com.android.server.adb.*`
   - hotspot eligibility checks
   - suppression or redirection of network-change logic that would disable hotspot-based wireless debugging

Changes that touch one side often require matching changes on the other.

## Current compatibility reality

Treat the following as the current baseline unless the user provides fresh evidence from a different branch/build:

- The repo was originally written for Android 15.
- The Settings-side hook surface is still broadly plausible on Android 16.
- The main Android 16 risk is **framework-side drift** in `com.android.server.adb.*`.
- In particular, Android 16 work must assume that:
  - `AdbConnectionInfo` may be top-level instead of nested inside `AdbDebuggingManager`
  - ADB Wi‑Fi network monitoring may use top-level monitor / receiver classes instead of anonymous inner classes
  - older class-name assumptions are unsafe unless verified on the target AOSP branch

## Required engineering posture

Be methodical.

- Separate **observation** from **inference**.
- Prefer **state inspection** before changing code.
- Change **one variable at a time**.
- Do not “fix” compatibility by broad blind hooking.
- Do not assume hidden/internal class names are stable across Android releases.
- Do not assume Pixel-specific behaviour without confirming it in AOSP or runtime evidence.
- If a runtime path is uncertain, build in **capability probing** and **fallbacks**.

## How to work on Android 16 compatibility

When modifying ADB/framework hooks:

1. Verify the relevant symbol(s) on the intended AOSP branch before editing logic.
2. Prefer existence checks and ordered fallbacks over a single hardcoded class name.
3. Wrap reflective lookups behind small helper functions where practical.
4. Log which branch/path was selected so runtime behaviour is diagnosable from LSPosed logs.
5. Fail soft: if one candidate path is absent, try the next candidate; only then log a precise failure.

### Expected compatibility strategy

For framework-side classes, prefer patterns like:
- probe multiple class names in a deterministic order
- probe multiple hook targets for newer/older branches
- preserve old behaviour where still valid
- keep Android 15 compatibility unless the task explicitly allows dropping it

Examples of expected migration patterns:
- `AdbConnectionInfo`: try top-level class first, then legacy nested class
- receiver/monitor logic: prefer explicit top-level classes where present; only fall back to anonymous-inner scanning for older branches

## Legacy API track vs modern API 101 track

Treat these as **separate workstreams**.

### Track A — legacy XposedBridge module, improved Android 16 compatibility
This is the default track.

Allowed changes:
- update hook targets
- add compatibility probing
- raise compile/target SDK where appropriate
- improve logging, docs, CI, and build reliability
- keep `assets/xposed_init` and legacy Xposed entry structure

### Track B — real modern libxposed / API 101 migration
Only do this if explicitly requested.

This is a structural port, not a small patch. It likely requires:
- replacing legacy Xposed API usage
- moving module metadata to modern locations
- changing entrypoint mechanics
- revisiting hook helper usage and framework assumptions

Do not partially mix Track A and Track B in the same change unless the task explicitly asks for a staged migration.

## Kotlin / Android coding expectations

- Use Kotlin idiomatically but keep reflection-heavy code straightforward.
- Prefer small helper functions over deeply nested try/catch blocks.
- Narrow exception handling where practical.
- Keep log messages stable and grep-friendly; prefix with `HotspotAdb:`.
- Avoid abstraction layers that obscure which Android symbol is being hooked.
- Do not introduce coroutine complexity unless it clearly solves a real problem.
- Prefer deterministic control flow over cleverness.

## Hooking guidelines

When adding or changing hooks:

- Document **why that symbol is chosen**.
- State whether the hook is for Settings UI, framework enable-path logic, or runtime network-state suppression.
- Do not suppress events broadly unless you can explain the exact ADB/Wi‑Fi codepath affected.
- Avoid hooks that mask failures without preserving the original behaviour when hotspot mode is not active.
- Keep hotspot gating explicit: only alter behaviour when hotspot mode is actually active.

## Hotspot-specific rules

The hotspot helper logic is heuristic by nature.

- Do not assume interface names are universal.
- Avoid regressing existing interface-name handling unless you have evidence.
- Distinguish station Wi‑Fi IP from hotspot/AP IP.
- If changing IP discovery, preserve backward compatibility and document the exact reason.
- Be careful with trust identity behaviour tied to SSID/BSSID; do not change synthetic identity behaviour casually.

## Build, lint, and validation

This repo has CI but no device-side automated tests. Every non-trivial change should at minimum preserve local build health.

Run when relevant:
- `./gradlew ktlintCheck detekt assembleDebug`
- `./gradlew assembleRelease` for release-related edits

If changing Gradle/SDK levels, verify:
- build still succeeds
- manifest metadata still matches module packaging expectations
- generated APK is still installable as an LSPosed/Xposed module

## Documentation expectations

When making compatibility edits, update docs with technical precision.

- Do not leave README claiming only Android 15 if the code has been intentionally updated for Android 16.
- Do not claim Android 16 support until the framework hook path has been updated and validated.
- Prefer explicit wording like “supported”, “expected to work”, or “experimental” based on evidence.

## Pull request / change output expectations

When asked to make a change, produce:
1. the code change
2. a short rationale tied to Android internals
3. the exact symbols/classes affected
4. risks / branch assumptions
5. the build or validation steps run

## Avoid these failure modes

- blindly hardcoding one Android 16 internal class name
- replacing specific hooks with broad global interception
- mixing modern API 101 migration changes into a legacy-compat patch without being asked
- changing hotspot trust identity semantics without justification
- updating README claims ahead of actual framework-hook compatibility
- treating this as a normal app-only Android project

## If uncertain

Stop and inspect the current AOSP symbol layout first. In this project, wrong certainty is worse than an incomplete patch.
