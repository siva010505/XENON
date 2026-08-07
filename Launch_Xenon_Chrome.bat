@echo off
set CHROME_EXE="C:\Program Files\Google\Chrome\Application\chrome.exe"
set EXT_PATH="%~dp0extension"
set PROFILE_PATH="%~dp0chrome_profile"

echo Starting Xenon Chrome with Debugging Port 9222 and auto-loaded extension...
start "" %CHROME_EXE% --remote-debugging-port=9222 --user-data-dir=%PROFILE_PATH% --load-extension=%EXT_PATH%
