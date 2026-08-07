@echo off
REM Install Browser Use native messaging host for Chrome
REM Run as Administrator for system-wide install

cd /d "%~dp0"

echo Installing Browser Use native messaging host...
powershell -ExecutionPolicy Bypass -File "install_host.ps1" %*

pause