@echo off
echo ========================================================
echo Xenon Native Messaging Setup
echo ========================================================
echo.
echo Please open Google Chrome and go to: chrome://extensions/
echo Find "Xenon" and copy the 32-letter Extension ID.
echo.
set /p EXT_ID="Paste Extension ID here: "

set "DIR=%~dp0"
set "JSON_PATH=%DIR%com.xenon.server.json"
set "BAT_PATH=%DIR%host_launcher.bat"
:: Escape backslashes for JSON
set "BAT_PATH=%BAT_PATH:\=\\%"

echo { > "%JSON_PATH%"
echo   "name": "com.xenon.server", >> "%JSON_PATH%"
echo   "description": "Xenon Native Messaging Host", >> "%JSON_PATH%"
echo   "path": "%BAT_PATH%", >> "%JSON_PATH%"
echo   "type": "stdio", >> "%JSON_PATH%"
echo   "allowed_origins": [ >> "%JSON_PATH%"
echo     "chrome-extension://%EXT_ID%/" >> "%JSON_PATH%"
echo   ] >> "%JSON_PATH%"
echo } >> "%JSON_PATH%"

:: Register in HKCU
REG ADD "HKCU\Software\Google\Chrome\NativeMessagingHosts\com.xenon.server" /ve /t REG_SZ /d "%JSON_PATH%" /f

echo.
echo ========================================================
echo SUCCESS! Native Messaging Host installed successfully.
echo You can now use the Xenon Chrome extension to boot the server automatically.
echo ========================================================
pause
