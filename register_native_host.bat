@echo off
set REG_KEY=HKCU\Software\Google\Chrome\NativeMessagingHosts\com.xenon.server
set MANIFEST_PATH=%~dp0extension\com.xenon.server.json

echo Registering Xenon Native Messaging Host in Windows Registry...
REG ADD "%REG_KEY%" /ve /t REG_SZ /d "%MANIFEST_PATH%" /f

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================================
    echo SUCCESS: Xenon Native Host successfully registered!
    echo Manifest: %MANIFEST_PATH%
    echo ========================================================
) else (
    echo.
    echo ERROR: Failed to register Native Host in Windows Registry.
)
pause
