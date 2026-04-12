# Copilot repository instructions

This repository is an Android Xposed/LSPosed module, not a normal app-only project. It hooks both `com.android.settings` and the `android` framework scope to allow native Wireless Debugging to operate over Wi‑Fi hotspot mode.

Assume the current codebase is a **legacy XposedBridge module** (`de.robv.android.xposed:api:82`, `assets/xposed_init`) unless a task explicitly requests a modern libxposed / API 101 migration.

When proposing or editing code:
- inspect current hook targets before changing them
- separate Settings-process UI hooks from framework / `system_server` hooks
- preserve hotspot-only behaviour changes
- prefer capability probing and fallbacks for Android-version drift
- keep log output precise and prefixed with `HotspotAdb:`
- avoid broad interception that could affect non-hotspot wireless debugging

For Android 16 work, treat framework-side drift in `com.android.server.adb.*` as the main risk area. Expect class ownership and monitoring structure changes across releases.

Do not claim Android 16 or API 101 support unless the relevant code path has actually been updated and validated.

Preferred validation for non-trivial changes:
- `./gradlew ktlintCheck detekt assembleDebug`
- update docs if compatibility claims changed
