---
applyTo: "app/src/main/kotlin/**/*.kt,app/src/main/AndroidManifest.xml,app/build.gradle.kts,README.md"
---

This repository contains Android hook code for LSPosed/Xposed.

When working on files matched by this instruction:

- Treat hidden/internal Android classes as unstable across Android versions.
- Verify symbol names and ownership before changing reflective hook code.
- Prefer ordered fallbacks for cross-version compatibility instead of a single hardcoded class path.
- Keep legacy XposedBridge compatibility unless the task explicitly requests modern libxposed / API 101 migration.
- Maintain the separation between:
  - Settings UI hook logic
  - framework / `system_server` ADB logic
  - hotspot helper heuristics
- Keep hotspot-only gating explicit.
- Avoid behaviour changes that affect normal client-mode wireless debugging.
- When changing compatibility claims in `README.md`, align them with the actual implemented and validated code path.
- When changing Gradle/manifest metadata, preserve LSPosed/Xposed module packaging semantics.

Expected output for substantial changes:
- mention the exact Android internal symbols/classes touched
- mention branch/version assumptions
- mention validation commands run
