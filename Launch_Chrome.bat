@echo off
echo =========================================
echo Closing background Chrome processes...
echo =========================================
taskkill /F /IM chrome.exe /T >nul 2>&1
timeout /t 2 >nul

echo.
echo =========================================
echo Starting Chrome for Xenon Agent...
echo =========================================
start chrome --remote-debugging-port=9222 --user-data-dir="%LOCALAPPDATA%\Google\Chrome\XenonProfile"
exit
