# Host-to-Client ADB over Hotspot

This document details how `hotspotadb` enables ADB connections over a Wi-Fi hotspot, focusing on two distinct directions of connection:

## Direction A: Client → Host (Core Module Feature)
A workstation, phone, or tablet connected to the Pixel host's hotspot connects to the Pixel host's own Wireless Debugging endpoint.
This is the core behaviour enabled by the `hotspotadb` module. By default, Android requires a station Wi-Fi connection for Wireless Debugging. The `hotspotadb` module hooks the framework and settings to allow Wireless Debugging to remain active while the phone acts as a hotspot (SoftAP), allowing clients on that hotspot network to pair and connect to the host.

## Direction B: Host → Client (New Workflow)
The Pixel hotspot host runs an adb client locally (e.g., using Termux) and connects to the Wireless Debugging endpoint on another Android device that has joined the Pixel's hotspot.

This document serves as a guide to achieving Direction B reliably.

### Why Direction B requires a local ADB client
To connect *from* the host *to* the client, the host itself must run an ADB client and server. The Android system does not provide a built-in user-facing ADB client for connecting to other devices. Termux, a terminal emulator and Linux environment app for Android, provides a robust, maintained ADB client package (`android-tools`) that can run directly on the Pixel host.

### Target device requirements
The target/client Android device (the one you are connecting *to*) must have Wireless Debugging enabled in Developer Options. Crucially, it must display its own pairing and connection ports.

### Host IP vs Client IP
When Wireless Debugging is enabled on the Pixel host (while running `hotspotadb`), the IP address shown on the Pixel's Wireless Debugging screen is the *host AP IP* (the IP of the hotspot interface itself). It is *not* the IP of the target client device. You must look at the target client device's screen to find its assigned IP address on the hotspot network, as well as its pairing and connect ports.

### Android 16 and mDNS Limitations
For this workflow, Android 16 is explicitly treated as using the current Wireless Debugging pairing/connect model (pre-ADB-Wi-Fi-2.0, which is planned for Android 17+).

Modern Android Wireless Debugging relies heavily on mDNS for discovery (`_adb-tls-pairing._tcp` and `_adb-tls-connect._tcp`). However, mDNS broadcast and discovery are often unreliable or blocked over hotspot/SoftAP network interfaces due to tethering routing rules or firewall configurations. Empty mDNS output means the network does not support automatic discovery.

Because of this, **direct IP:port pairing and connecting is the primary and most reliable method.** mDNS is considered an optional diagnostic tool.

### Primary Termux Command Sequence

This sequence runs on the Pixel host device using Termux. Do not rely on mDNS automatic discovery.

1. **Ensure ADB is installed:**
   ```bash
   pkg install android-tools
   ```

2. **Pair to the target device:**
   Find the IP, pairing port, and pairing code on the target device's "Pair device with pairing code" screen.
   ```bash
   adb pair <target_client_ip>:<pairing_port>
   ```
   *You will be prompted to enter the pairing code.*

3. **Connect to the target device:**
   Find the connection port on the target device's main Wireless Debugging screen (this port is different from the pairing port).
   ```bash
   adb connect <target_client_ip>:<connect_port>
   ```

4. **Verify the connection:**
   ```bash
   adb devices -l
   ```

*Use the included `tools/hotspotadb-adb-netcheck.sh` script to streamline this process safely.*

### Troubleshooting Decision Tree

If you encounter issues during the host-to-client connection:

#### mDNS empty
* **Meaning:** Automatic discovery is unavailable on this network.
* **Action:** Use direct IP:port from the target's Wireless Debugging screen. Do not treat this as fatal.

#### Pairing port unreachable
* **Likely causes:** Wrong target IP, target not connected to Pixel hotspot, Wireless Debugging pairing dialog closed, pairing port rotated, or a hotspot firewall/routing issue.
* **Action:** Reopen the target pairing dialog, re-check the target IP, run the `hotspotadb-adb-netcheck.sh` helper, and collect logs if still failing.

#### Pair succeeds but connect fails
* **Likely causes:** Using the pairing port instead of the connect port, the connect port changed, the target's Wireless Debugging toggled/restarted, or stale adb server state.
* **Action:** Use the connect port from the main Wireless Debugging screen (not the pairing dialog), run `adb kill-server && adb start-server`, and retry `adb connect <ip>:<connect_port>`.

#### Connected but unauthorised/offline
* **Likely causes:** Stale adb key, target prompt not accepted, or adb server state mismatch.
* **Action:** Accept the prompt on the target device. Revoke debugging authorisations only as a later recovery step. Restart the adb server and reconnect.

#### Pixel host Wireless Debugging disables itself when hotspot state changes
* **Likely causes:** Android 16 framework network callback path not fully suppressed, hook not installed due to class/signature drift, or context extraction failure.
* **Action:** Collect `HotspotAdb`, `adbd`, and `AdbDebuggingManager` logs. Inspect the Xposed/LSPosed hook install logs to fix hook selection rather than masking the symptom.

### Limitations and Non-Goals
* **No automatic discovery:** Due to mDNS limitations on hotspots, automatic discovery is not guaranteed. Manual IP:port entry is the supported method.
* **No client-to-client routing:** This guide focuses only on Host ↔ Connected Client communication. Communication between two different clients connected to the same hotspot is out of scope and may be blocked by Android tethering rules.
* **Security:** This workflow uses the standard, secure Android Wireless Debugging (TLS/pairing). It **does not** enable or rely on insecure, unauthenticated persistent `adb tcpip 5555` listeners.
