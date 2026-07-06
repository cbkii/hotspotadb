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

log() {
    printf 'HotspotAdb: %s\n' "$*"
}

warn() {
    printf 'HotspotAdb: Warning: %s\n' "$*" >&2
}

error() {
    printf 'HotspotAdb: Error: %s\n' "$*" >&2
}

have_timeout=0
if command -v timeout >/dev/null 2>&1; then
    have_timeout=1
fi

run_bounded() {
    local seconds=$1
    shift
    if ((have_timeout == 1)); then
        timeout "$seconds" "$@"
        return $?
    fi

    warn "timeout is not installed; skipping bounded command: $*"
    warn "If using Termux, install it via: pkg install coreutils"
    return 124
}

print_usage() {
    log "Usage: $0 [options]"
    log "Options:"
    log "  --target-ip <ip>      Target device IP address"
    log "  --pair-port <port>    Target device pairing port"
    log "  --connect-port <port> Target device connect port"
    log "  --pair                Run adb pair with target-ip and pair-port"
    log "  --connect             Run adb connect with target-ip and connect-port"
    log "  --collect-logs        Collect relevant adb/hotspot logs if requested"
    log "  -h, --help            Show this help message"
}

while [[ "$#" -gt 0 ]]; do
    case "$1" in
        --target-ip)
            if [[ -n "${2:-}" && "$2" != -* ]]; then
                TARGET_IP="$2"
                shift 2
            else
                error "--target-ip requires a non-empty value."
                print_usage
                exit 1
            fi
            ;;
        --pair-port)
            if [[ -n "${2:-}" && "$2" != -* ]]; then
                PAIR_PORT="$2"
                shift 2
            else
                error "--pair-port requires a non-empty value."
                print_usage
                exit 1
            fi
            ;;
        --connect-port)
            if [[ -n "${2:-}" && "$2" != -* ]]; then
                CONNECT_PORT="$2"
                shift 2
            else
                error "--connect-port requires a non-empty value."
                print_usage
                exit 1
            fi
            ;;
        --pair)
            DO_PAIR=true
            shift
            ;;
        --connect)
            DO_CONNECT=true
            shift
            ;;
        --collect-logs)
            COLLECT_LOGS=true
            shift
            ;;
        -h | --help)
            print_usage
            exit 0
            ;;
        *)
            error "Unknown parameter passed: $1"
            print_usage
            exit 1
            ;;
    esac
done

if [ "$DO_PAIR" = true ]; then
    if [ -z "$TARGET_IP" ] || [ -z "$PAIR_PORT" ]; then
        error "--pair requires both --target-ip and --pair-port."
        exit 1
    fi
fi

if [ "$DO_CONNECT" = true ]; then
    if [ -z "$TARGET_IP" ] || [ -z "$CONNECT_PORT" ]; then
        error "--connect requires both --target-ip and --connect-port."
        exit 1
    fi
fi

log "=== Host Identity ==="
if command -v getprop >/dev/null 2>&1; then
    log "Model: $(getprop ro.product.model 2>/dev/null)"
    log "Device: $(getprop ro.product.device 2>/dev/null)"
    log "Codename: $(getprop ro.build.product 2>/dev/null)"
    log "Android Version: $(getprop ro.build.version.release 2>/dev/null) (SDK $(getprop ro.build.version.sdk 2>/dev/null))"
else
    warn "getprop not found. Host identity details unavailable."
fi

HAS_ROOT=false
if command -v su >/dev/null 2>&1; then
    if run_bounded 3 su -c id >/dev/null 2>&1; then
        log "Root available: Yes"
        HAS_ROOT=true
    else
        log "Root available: No (su exists but access denied or timed out)"
    fi
else
    log "Root available: No"
fi
echo ""

log "=== Hotspot State & Interfaces ==="
if command -v ip >/dev/null 2>&1; then
    log "IP Routes (Hints for subnet/interfaces):"
    ip route | grep -E 'wlan|ap|swlan' || log "  No clear hotspot wlan routes found."
    echo ""
    log "Interface Addresses (excluding loopback):"
    ip -4 addr show | grep -E 'inet ' | grep -v '127.0.0.1' | sed 's/^ *//g'
else
    warn "ip command not found."
fi
echo ""

log "=== Connected Client Candidates ==="
log "Neighbour Table (ARP/NDP):"
if command -v ip >/dev/null 2>&1; then
    ip neigh show | grep -E 'wlan|ap|swlan' || log "  No wlan neighbours found."
elif command -v arp >/dev/null 2>&1; then
    arp -a || log "  No ARP entries found."
else
    warn "No ip or arp command found to list neighbours."
fi
echo ""

log "=== ADB Client Readiness ==="
if command -v adb >/dev/null 2>&1; then
    ADB_VERSION_OUT=$(run_bounded 5 adb version 2>/dev/null)
    if [ -n "$ADB_VERSION_OUT" ]; then
        printf '%s\n' "$ADB_VERSION_OUT" | head -n 1 | while read -r line; do log "$line"; done
    else
        warn "adb version unavailable or timed out."
    fi

    # Try server-status (newer adb versions)
    run_bounded 5 adb server-status >/dev/null 2>&1 || warn "adb server-status not supported, server down, or timed out."

    log "Current ADB devices:"
    run_bounded 5 adb devices -l || warn "adb devices command timed out."

    export ADB_MDNS=1
    log "mDNS Services (optional, with ADB_MDNS=1):"
    MDNS_OUT=$(run_bounded 5 adb mdns services 2>/dev/null)
    if [ -z "$MDNS_OUT" ]; then
        log "  mDNS services command returned empty. Automatic discovery is unavailable on this network."
    else
        echo "$MDNS_OUT" | while read -r line; do log "$line"; done
    fi
else
    warn "adb command not found. Please install android-tools (e.g. 'pkg install android-tools' in Termux)."
fi
echo ""

if [ "$COLLECT_LOGS" = true ]; then
    log "=== Diagnostic Logs Collection ==="
    if [ "$HAS_ROOT" = true ]; then
        log "Dumpsys tethering (brief):"
        run_bounded 5 su -c "dumpsys tethering | grep -A 10 'Tether state'" || warn "Failed to dump tethering"

        log "Recent HotspotAdb logcat snippets:"
        run_bounded 5 su -c "logcat -d -s HotspotAdb | tail -n 20" || warn "Failed to fetch logcat"

        log "Recent adb/AdbDebuggingManager logcat snippets:"
        run_bounded 5 su -c "logcat -d -s adbd AdbDebuggingManager | tail -n 20" || warn "Failed to fetch logcat"
    else
        warn "Root is required to collect dumpsys and logcat diagnostics. Skipping."
    fi
    echo ""
fi

nc_supports_zero_io_timeout() {
    command -v nc >/dev/null 2>&1 || return 1

    local help_out
    help_out=$(run_bounded 3 nc -h 2>&1 || true)
    [[ "$help_out" == *"-z"* ]] || return 1
    [[ "$help_out" == *"-w"* ]] || return 1
    return 0
}

check_tcp() {
    local host=$1
    local port=$2

    if nc_supports_zero_io_timeout; then
        if nc -z -w 3 "$host" "$port" >/dev/null 2>&1; then
            return 0
        fi
    fi

    if run_bounded 3 bash -c '</dev/tcp/$1/$2' _ "$host" "$port" >/dev/null 2>&1; then
        return 0
    fi
    return 1
}

if [ -n "$TARGET_IP" ]; then
    log "=== Target Operations ==="

    if [ "$DO_PAIR" = true ] && [ -n "$PAIR_PORT" ]; then
        log "Testing TCP reachability to ${TARGET_IP}:${PAIR_PORT}..."
        if check_tcp "$TARGET_IP" "$PAIR_PORT"; then
            log "Port $PAIR_PORT reachable."
            if command -v adb >/dev/null 2>&1; then
                if [ -t 0 ]; then
                    log "Pairing with ${TARGET_IP}:${PAIR_PORT}..."
                    adb pair "${TARGET_IP}:${PAIR_PORT}"
                    PAIR_RES=$?
                    if [ $PAIR_RES -ne 0 ]; then
                        warn "Pairing failed."
                    else
                        log "Pairing step finished."
                    fi
                else
                    warn "Non-interactive shell detected."
                    warn "Cannot prompt for pairing code safely."
                    warn "Please run manually: adb pair ${TARGET_IP}:${PAIR_PORT}"
                fi
            else
                warn "Cannot pair: adb not found."
            fi
        else
            warn "Port $PAIR_PORT unreachable. Check IP, port, and ensure target is connected."
        fi
        echo ""
    fi

    if [ "$DO_CONNECT" = true ] && [ -n "$CONNECT_PORT" ]; then
        log "Testing TCP reachability to ${TARGET_IP}:${CONNECT_PORT}..."
        if check_tcp "$TARGET_IP" "$CONNECT_PORT"; then
            log "Port $CONNECT_PORT reachable."
            if command -v adb >/dev/null 2>&1; then
                log "Connecting to ${TARGET_IP}:${CONNECT_PORT}..."
                run_bounded 15 adb connect "${TARGET_IP}:${CONNECT_PORT}"
            else
                warn "Cannot connect: adb not found."
            fi
        else
            warn "Port $CONNECT_PORT unreachable. Check IP, port, and ensure target is connected."
        fi
    elif [ "$DO_CONNECT" = true ] && [ -z "$CONNECT_PORT" ]; then
        warn "--connect requested but no --connect-port provided."
    fi
    echo ""
fi

log "=== Summary ==="
log "Diagnostic script finished."
log "If you need to connect to a client device, ensure it's on the hotspot, find its IP and ports, and run this script with --target-ip, --pair-port <port> --pair, and --connect-port <port> --connect."
