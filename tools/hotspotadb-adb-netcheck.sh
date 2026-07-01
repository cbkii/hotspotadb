#!/usr/bin/env bash

# hotspotadb-adb-netcheck.sh
# Diagnostic script to help identify host IPs and perform adb actions
# safely over a hotspot connection.

TARGET_IP=""
PAIR_PORT=""
CONNECT_PORT=""
DO_PAIR=false
DO_CONNECT=false
COLLECT_LOGS=false

print_usage() {
    echo "Usage: $0 [options]"
    echo "Options:"
    echo "  --target-ip <ip>      Target device IP address"
    echo "  --pair-port <port>    Target device pairing port"
    echo "  --connect-port <port> Target device connect port"
    echo "  --pair                Run adb pair with target-ip and pair-port"
    echo "  --connect             Run adb connect with target-ip and connect-port"
    echo "  --collect-logs        Collect relevant adb/hotspot logs if requested"
    echo "  -h, --help            Show this help message"
}

while [[ "$#" -gt 0 ]]; do
    case "$1" in
        --target-ip)
            if [[ -n "${2:-}" && "$2" != -* ]]; then
                TARGET_IP="$2"
                shift 2
            else
                echo "Error: --target-ip requires a non-empty value."
                print_usage
                exit 1
            fi
            ;;
        --pair-port)
            if [[ -n "${2:-}" && "$2" != -* ]]; then
                PAIR_PORT="$2"
                shift 2
            else
                echo "Error: --pair-port requires a non-empty value."
                print_usage
                exit 1
            fi
            ;;
        --connect-port)
            if [[ -n "${2:-}" && "$2" != -* ]]; then
                CONNECT_PORT="$2"
                shift 2
            else
                echo "Error: --connect-port requires a non-empty value."
                print_usage
                exit 1
            fi
            ;;
        --pair) DO_PAIR=true; shift ;;
        --connect) DO_CONNECT=true; shift ;;
        --collect-logs) COLLECT_LOGS=true; shift ;;
        -h|--help) print_usage; exit 0 ;;
        *) echo "Unknown parameter passed: $1"; print_usage; exit 1 ;;
    esac
done

echo "=== Host Identity ==="
if command -v getprop >/dev/null 2>&1; then
    echo "Model: $(getprop ro.product.model 2>/dev/null)"
    echo "Device: $(getprop ro.product.device 2>/dev/null)"
    echo "Codename: $(getprop ro.build.product 2>/dev/null)"
    echo "Android Version: $(getprop ro.build.version.release 2>/dev/null) (SDK $(getprop ro.build.version.sdk 2>/dev/null))"
else
    echo "Warning: getprop not found. Host identity details unavailable."
fi

HAS_ROOT=false
if command -v su >/dev/null 2>&1; then
    echo "Root available: Yes"
    HAS_ROOT=true
else
    echo "Root available: No"
fi
echo ""

echo "=== Hotspot State & Interfaces ==="
if command -v ip >/dev/null 2>&1; then
    echo "IP Routes (Hints for subnet/interfaces):"
    ip route | grep -E 'wlan|ap|swlan' || echo "  No clear hotspot wlan routes found."
    echo ""
    echo "Interface Addresses (Filtering loopback and non-up):"
    ip -4 addr show | grep -E 'inet ' | grep -v '127.0.0.1' | sed 's/^ *//g'
else
    echo "Warning: ip command not found."
fi
echo ""

echo "=== Connected Client Candidates ==="
echo "Neighbour Table (ARP/NDP):"
if command -v ip >/dev/null 2>&1; then
    ip neigh show | grep -E 'wlan|ap|swlan' || echo "  No wlan neighbours found."
elif command -v arp >/dev/null 2>&1; then
    arp -a || echo "  No ARP entries found."
else
    echo "Warning: No ip or arp command found to list neighbours."
fi
echo ""

echo "=== ADB Client Readiness ==="
if command -v adb >/dev/null 2>&1; then
    adb version | head -n 1

    # Try server-status (newer adb versions)
    adb server-status >/dev/null 2>&1 || echo "Warning: adb server-status not supported or server down."

    echo "Current ADB devices:"
    timeout 5 adb devices -l || echo "Warning: adb devices command timed out."

    export ADB_MDNS=1
    echo "mDNS Services (optional, with ADB_MDNS=1):"
    MDNS_OUT=$(timeout 5 adb mdns services 2>/dev/null)
    if [ -z "$MDNS_OUT" ]; then
         echo "  mDNS services command returned empty. Automatic discovery is unavailable on this network."
    else
         echo "$MDNS_OUT"
    fi
else
    echo "Warning: adb command not found. Please install android-tools (e.g. 'pkg install android-tools' in Termux)."
fi
echo ""

if [ "$COLLECT_LOGS" = true ]; then
    echo "=== Diagnostic Logs Collection ==="
    if [ "$HAS_ROOT" = true ]; then
        echo "Dumpsys tethering (brief):"
        su -c "dumpsys tethering | grep -A 10 'Tether state'" || echo "Failed to dump tethering"

        echo "Recent HotspotAdb logcat snippets:"
        su -c "logcat -d -s HotspotAdb | tail -n 20" || echo "Failed to fetch logcat"

        echo "Recent adb/AdbDebuggingManager logcat snippets:"
        su -c "logcat -d -s adbd AdbDebuggingManager | tail -n 20" || echo "Failed to fetch logcat"
    else
        echo "Root is required to collect dumpsys and logcat diagnostics. Skipping."
    fi
    echo ""
fi

check_tcp() {
    local host=$1
    local port=$2
    if command -v nc >/dev/null 2>&1; then
        if nc -z -w 3 "$host" "$port"; then
            return 0
        fi
    elif timeout 3 bash -c "</dev/tcp/$host/$port" >/dev/null 2>&1; then
        return 0
    fi
    return 1
}

if [ -n "$TARGET_IP" ]; then
    echo "=== Target Operations ==="

    if [ "$DO_PAIR" = true ] && [ -n "$PAIR_PORT" ]; then
        echo "Testing TCP reachability to ${TARGET_IP}:${PAIR_PORT}..."
        if check_tcp "$TARGET_IP" "$PAIR_PORT"; then
            echo "Port $PAIR_PORT reachable."
            if command -v adb >/dev/null 2>&1; then
                if [ -t 0 ]; then
                    echo "Pairing with ${TARGET_IP}:${PAIR_PORT}..."
                    timeout 30 adb pair "${TARGET_IP}:${PAIR_PORT}"
                    PAIR_RES=$?
                    if [ $PAIR_RES -ne 0 ]; then
                        echo "Pairing failed or timed out."
                    else
                        echo "Pairing step finished."
                    fi
                else
                    echo "Non-interactive shell detected."
                    echo "Cannot prompt for pairing code safely."
                    echo "Please run manually: adb pair ${TARGET_IP}:${PAIR_PORT}"
                fi
            else
                echo "Cannot pair: adb not found."
            fi
        else
            echo "Port $PAIR_PORT unreachable. Check IP, port, and ensure target is connected."
        fi
        echo ""
    fi

    if [ "$DO_CONNECT" = true ] && [ -n "$CONNECT_PORT" ]; then
        echo "Testing TCP reachability to ${TARGET_IP}:${CONNECT_PORT}..."
        if check_tcp "$TARGET_IP" "$CONNECT_PORT"; then
            echo "Port $CONNECT_PORT reachable."
            if command -v adb >/dev/null 2>&1; then
                echo "Connecting to ${TARGET_IP}:${CONNECT_PORT}..."
                timeout 15 adb connect "${TARGET_IP}:${CONNECT_PORT}"
            else
                echo "Cannot connect: adb not found."
            fi
        else
            echo "Port $CONNECT_PORT unreachable. Check IP, port, and ensure target is connected."
        fi
    elif [ "$DO_CONNECT" = true ] && [ -z "$CONNECT_PORT" ]; then
        echo "Warning: --connect requested but no --connect-port provided."
    fi
    echo ""
fi

echo "=== Summary ==="
echo "Diagnostic script finished."
echo "If you need to connect to a client device, ensure it's on the hotspot, find its IP and ports, and run this script with --target-ip, --pair-port <port> --pair, and --connect-port <port> --connect."
