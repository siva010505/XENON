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

def find_chrome_path():
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe")
        path, _ = winreg.QueryValueEx(key, "")
        if os.path.exists(path):
            return path
    except Exception:
        pass
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe")
        path, _ = winreg.QueryValueEx(key, "")
        if os.path.exists(path):
            return path
    except Exception:
        pass
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe")
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return r"C:\Program Files\Google\Chrome\Application\chrome.exe"

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
subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], check=False,
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
res_pip = subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "-r",
                          os.path.join(PROJECT_DIR, "requirements.txt")], check=False)
if res_pip.returncode != 0:
    print("\nWARNING: Dependency installation encountered errors. Please check your internet connection or Python setup.")

print("\n[2/5] Installing Playwright Chromium Browser...")
subprocess.run([sys.executable, "-m", "pip", "install", "playwright"], check=False)
res_pw = subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=False)

print("\n[3/5] Updating Chrome Native Messaging Manifest & Launcher...")
# Write run_native_host.bat with this Python executable
bat_content = f'@echo off\n"{sys.executable}" "%~dp0native_host.py" %*\n'
with open(BAT_PATH, "w") as f:
    f.write(bat_content)

# Also patch native_host.py so it always uses the correct Python for server.py
native_host_path = os.path.join(PROJECT_DIR, "native_host.py")
try:
    with open(native_host_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    new_lines = []
    for line in lines:
        if line.strip().startswith("PYTHON_EXECUTABLE"):
            new_lines.append('PYTHON_EXECUTABLE = r"' + sys.executable + '"\n')
        else:
            new_lines.append(line)
    with open(native_host_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    print(f"  -> Patched native_host.py to use: {sys.executable}")
except Exception as e:
    print(f"  -> Warning: Could not patch native_host.py: {e}")

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
chrome_exe = find_chrome_path()
ps_script = f"""
$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [Environment]::GetFolderPath('Desktop')
$Shortcut = $WshShell.CreateShortcut("$DesktopPath\\Xenon Chrome.lnk")
$Shortcut.TargetPath = '{chrome_exe}'
$Shortcut.Arguments = '--remote-debugging-port=9222 --user-data-dir="{PROFILE_DIR}" --load-extension="{EXT_DIR}"'
$Shortcut.IconLocation = '{chrome_exe},0'
$Shortcut.Save()
"""
subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_script], check=False)

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
