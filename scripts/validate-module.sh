#!/usr/bin/env bash
set -euo pipefail

# Explicit writes are allowed only in the two user-facing toggle implementations
# and in HotspotHelper's system_server readiness publication. A broad hook of
# Settings.Global.putInt remains forbidden because it can block user-requested
# Wireless Debugging disables.
UNEXPECTED_PUTINT="$({
    grep -R "Settings.Global.putInt" -n app/src/main || true
} | grep -Ev '/(SettingsHook|FixedEndpointSettingsHook|HotspotHelper)\.kt:' | grep -Ev ':[0-9]+:[[:space:]]*(//|\*)' || true)"
if [[ -n "$UNEXPECTED_PUTINT" ]]; then
    printf '%s\n' "$UNEXPECTED_PUTINT" >&2
    echo "Unexpected Settings.Global.putInt usage outside approved explicit state writes" >&2
    exit 1
fi

BROAD_INTERCEPT="$({
    grep -R -E 'hookSettingsGlobal|Settings\.Global(::class\.java|\.class)|findMethod\([^)]*putInt' -n app/src/main || true
} | grep -Ev ':[0-9]+:[[:space:]]*(//|\*)' || true)"
if [[ -n "$BROAD_INTERCEPT" ]]; then
    printf '%s\n' "$BROAD_INTERCEPT" >&2
    echo "Broad Settings.Global.putInt interception is forbidden" >&2
    exit 1
fi

shopt -s nullglob
APK_LIST=(app/build/outputs/apk/debug/*.apk)
shopt -u nullglob
if [[ ${#APK_LIST[@]} -ne 1 ]]; then
    echo "Expected exactly 1 debug APK, found ${#APK_LIST[@]}: ${APK_LIST[*]}" >&2
    exit 1
fi
APK="${APK_LIST[0]}"
for f in META-INF/xposed/module.prop META-INF/xposed/java_init.list META-INF/xposed/scope.list; do
    unzip -p "$APK" "$f" >/dev/null
    echo "OK: $f"
done

unzip -p "$APK" META-INF/xposed/java_init.list | grep -qF "io.cb.hotspotadb.HotspotAdbModule"
unzip -p "$APK" META-INF/xposed/scope.list | grep -qF "android"
unzip -p "$APK" META-INF/xposed/scope.list | grep -qF "com.android.settings"
unzip -p "$APK" META-INF/xposed/module.prop | grep -qF "minApiVersion=101"
unzip -p "$APK" META-INF/xposed/module.prop | grep -qF "targetApiVersion=101"
unzip -p "$APK" META-INF/xposed/module.prop | grep -qF "staticScope=true"

echo "Module validation passed"
