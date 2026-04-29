#!/usr/bin/env bash
set -euo pipefail

grep -R "Settings.Global.putInt" -n app/src/main | grep -v "SettingsHook.kt" && {
  echo "Unexpected Settings.Global.putInt usage outside injected toggle" >&2
  exit 1
} || true

APK="$(ls app/build/outputs/apk/debug/*.apk | head -1)"
for f in META-INF/xposed/module.prop META-INF/xposed/java_init.list META-INF/xposed/scope.list; do
  unzip -p "$APK" "$f" >/dev/null
  echo "OK: $f"
done

unzip -p "$APK" META-INF/xposed/java_init.list | grep -qF "io.drsr.hotspotadb.HotspotAdbModule"
unzip -p "$APK" META-INF/xposed/scope.list | grep -qF "android"
unzip -p "$APK" META-INF/xposed/scope.list | grep -qF "com.android.settings"
unzip -p "$APK" META-INF/xposed/module.prop | grep -qF "minApiVersion=101"
unzip -p "$APK" META-INF/xposed/module.prop | grep -qF "targetApiVersion=101"
unzip -p "$APK" META-INF/xposed/module.prop | grep -qF "staticScope=true"

echo "Module validation passed"
