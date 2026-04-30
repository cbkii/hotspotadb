#!/usr/bin/env bash
set -euo pipefail

grep -R "Settings.Global.putInt" -n app/src/main | grep -v "SettingsHook.kt" | grep -Ev ":[0-9]+:[[:space:]]*(//|\*)" && {
  echo "Unexpected Settings.Global.putInt usage outside injected toggle" >&2
  exit 1
} || true

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

unzip -p "$APK" META-INF/xposed/java_init.list | grep -qF "io.cbkii.hotspotadb.HotspotAdbModule"
unzip -p "$APK" META-INF/xposed/scope.list | grep -qF "android"
unzip -p "$APK" META-INF/xposed/scope.list | grep -qF "com.android.settings"
unzip -p "$APK" META-INF/xposed/module.prop | grep -qF "minApiVersion=101"
unzip -p "$APK" META-INF/xposed/module.prop | grep -qF "targetApiVersion=101"
unzip -p "$APK" META-INF/xposed/module.prop | grep -qF "staticScope=true"

echo "Module validation passed"
