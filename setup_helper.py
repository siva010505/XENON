import os
import sys
import json
import subprocess

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
EXT_DIR = os.path.join(PROJECT_DIR, "extension")
PROFILE_DIR = os.path.join(PROJECT_DIR, "chrome_profile")
MANIFEST_PATH = os.path.join(EXT_DIR, "com.xenon.server.json")
BAT_PATH = os.path.join(PROJECT_DIR, "run_native_host.bat")

print("========================================================")
print("               XENON AUTOMATED SETUP")
print("========================================================\n")

v = sys.version_info
if v < (3, 11):
    print("========================================================")
    print("❌ ERROR: PYTHON VERSION INCOMPATIBLE!")
    print(f"Xenon requires Python 3.11 or newer.")
    print(f"Your system is currently running Python {v.major}.{v.minor}.{v.micro} ({sys.executable}).")
    print("")
    print("Please download and install Python 3.11 or 3.12:")
    print("👉 Download link: https://www.python.org/downloads/")
    print("========================================================\n")
    sys.exit(1)

print("[1/5] Installing Python Dependencies...")
res_pip = subprocess.run([sys.executable, "-m", "pip", "install", "-r", os.path.join(PROJECT_DIR, "requirements.txt")], check=False)
if res_pip.returncode != 0:
    print("\n❌ WARNING: Dependency installation encountered errors. Please check your internet connection or Python setup.")

print("\n[2/5] Installing Playwright Chromium Browser...")
res_pw = subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=False)

print("\n[3/5] Updating Chrome Native Messaging Manifest...")
data = {
    "name": "com.xenon.server",
    "description": "Xenon Background Server Launcher",
    "path": BAT_PATH,
    "type": "stdio",
    "allowed_origins": [
        "chrome-extension://bgcejckonpajffecfflnoplmmdpdahgg/"
    ]
}
with open(MANIFEST_PATH, "w") as f:
    json.dump(data, f, indent=2)

print("\n[4/5] Registering Xenon Native Messaging Host in Windows Registry...")
reg_key = r"HKCU\Software\Google\Chrome\NativeMessagingHosts\com.xenon.server"
subprocess.run(["REG", "ADD", reg_key, "/ve", "/t", "REG_SZ", "/d", MANIFEST_PATH, "/f"], check=False)

print("\n[5/5] Creating 'Xenon Chrome' Desktop Shortcut...")
ps_script = f"""
$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [Environment]::GetFolderPath('Desktop')
$Shortcut = $WshShell.CreateShortcut("$DesktopPath\\Xenon Chrome.lnk")
$Shortcut.TargetPath = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
$Shortcut.Arguments = '--remote-debugging-port=9222 --user-data-dir="{PROFILE_DIR}" --load-extension="{EXT_DIR}"'
$Shortcut.IconLocation = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe,0'
$Shortcut.Save()
"""
subprocess.run(["powershell", "-Command", ps_script], check=False)

print("\n========================================================")
print("SUCCESS: XENON SETUP COMPLETE!")
print("")
print("NEXT STEPS FOR YOU:")
print("1. Double-click the 'Xenon Chrome' shortcut on your Desktop.")
print("2. Sign in to your Google / Gmail account in Chrome.")
print("3. Open chrome://extensions, enable 'Developer Mode' (top-right toggle),")
print("   and click 'Load unpacked' -> select the 'extension' folder from this project.")
print("4. Open the Xenon Side Panel in Chrome, enter your AI API Key in Settings once,")
print("   and start automating tasks!")
print("========================================================\n")
