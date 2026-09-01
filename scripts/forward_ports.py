#!/usr/bin/env python3
"""Port Forwarding & Phone Connectivity Helper for DisasterMesh Sentinel.

Helps connect physical Android phones via:
1. ADB Reverse (USB cable -> localhost:8000)
2. Local Wi-Fi (LAN IP detection & firewall instructions)
3. Public Cloud Tunnel (localtunnel / cloudflared / ngrok for any internet network)
"""

import os
import socket
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass



def get_local_ips() -> list[str]:
    ips = []
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None):
            ip = info[4][0]
            if ":" not in ip and not ip.startswith("127."):
                if ip not in ips:
                    ips.append(ip)
    except Exception:
        pass
    return ips


def find_adb_path() -> str:
    from shutil import which
    if which("adb"):
        return "adb"
    candidates = [
        r"C:\Users\alive\AppData\Local\Android\Sdk\platform-tools\adb.exe",
        os.path.join(os.environ.get("ANDROID_HOME", ""), "platform-tools", "adb.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Android", "Sdk", "platform-tools", "adb.exe"),
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return "adb"


def setup_adb_reverse():
    print("\n[1/3] Checking connected ADB Android devices for USB Port Forwarding...")
    adb_bin = find_adb_path()
    try:
        res = subprocess.run([adb_bin, "devices"], capture_output=True, text=True, timeout=5)
        lines = [line.strip() for line in res.stdout.splitlines() if line.strip() and not line.startswith("List")]
        if lines:
            print(f"  Found {len(lines)} Android device(s):")
            for dev in lines:
                print(f"    - {dev}")
            reverse_res = subprocess.run([adb_bin, "reverse", "tcp:8000", "tcp:8000"], capture_output=True, text=True)
            if reverse_res.returncode == 0:
                print("  [SUCCESS] Executed 'adb reverse tcp:8000 tcp:8000'!")
                print("  -> In the Android App, set Server URL to: http://127.0.0.1:8000")
            else:
                print(f"  [NOTE] 'adb reverse' returned: {reverse_res.stderr.strip()}")
        else:
            print("  No USB Android device detected. (Plug in phone with USB Debugging enabled if testing over USB).")
    except Exception as e:
        print(f"  ADB check skipped: {e}")


def show_lan_options():
    print("\n[2/3] Local Wi-Fi Connection URLs (Physical Phones on same Wi-Fi):")
    ips = get_local_ips()
    if ips:
        for ip in ips:
            print(f"  -> In the Android App, set Server URL to: http://{ip}:8000")
    else:
        print("  -> In the Android App, set Server URL to: http://<your-pc-ip>:8000")
    print("  -> Ensure Windows Firewall allows incoming connections on port 8000.")


def show_tunnel_options():
    print("\n[3/3] Public Internet Tunnel Options (Connect from anywhere / cellular):")
    print("  Option A (npx localtunnel):")
    print("    Run in a new terminal: npx -y localtunnel --port 8000")
    print("    Then paste the generated https://...loca.lt URL into the Android App Settings!")
    print("\n  Option B (Cloudflare Tunnel):")
    print("    Run: cloudflared tunnel --url http://localhost:8000")


def main():
    print("=" * 70)
    print(" DisasterMesh Sentinel — Phone Connectivity & Port Forwarding Helper")
    print("=" * 70)

    setup_adb_reverse()
    show_lan_options()
    show_tunnel_options()

    print("\n" + "=" * 70)
    print(" Backend Server command:")
    print("   python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000")
    print(" Dashboard Dev Server command:")
    print("   cd dashboard && npm run dev -- --host 0.0.0.0")
    print("=" * 70)


if __name__ == "__main__":
    main()
