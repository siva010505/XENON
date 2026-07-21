@echo off
echo ========================================================
echo Launching Dedicated Xenon Chrome Debugging Instance
echo ========================================================
echo.
echo Make sure you log in to your Google Account and any other 
echo websites here so Xenon can automate them!
echo.
echo Pin this window to your taskbar for easy access.
echo.
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="%LOCALAPPDATA%\Google\Chrome\User Data Xenon"
