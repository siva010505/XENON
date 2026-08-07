@echo off
title Xenon 1-Click Automated Setup
cd /d "%~dp0"

echo ========================================================
echo               XENON AUTOMATED SETUP
echo ========================================================
echo.

:: 1. Try py -3.11
py -3.11 --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    py -3.11 setup_helper.py
    goto :END
)

:: 2. Try py -3
py -3 --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    py -3 setup_helper.py
    goto :END
)

:: 3. Try python (if version >= 3.11)
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    python setup_helper.py
    goto :END
)

:: 4. If Python 3.11+ not found, download & launch Python installer
echo ⚠️ Python 3.11+ is required but was not found on your system.
echo Downloading official Python 3.11 installer from python.org...
echo.

set "INSTALLER=%TEMP%\python-3.11.9-amd64.exe"

curl.exe -sSL -o "%INSTALLER%" "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
if not exist "%INSTALLER%" (
    powershell -Command "(New-Object System.Net.WebClient).Headers.Add('User-Agent', 'Mozilla/5.0'); (New-Object System.Net.WebClient).DownloadFile('https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe', '%INSTALLER%')"
)

if exist "%INSTALLER%" (
    echo.
    echo Launching Python 3.11 Installer...
    echo 📌 IMPORTANT: In the installer window, make sure to check "Add python.exe to PATH"!
    echo.
    start /wait "" "%INSTALLER%" /passive PrependPath=1
    if errorlevel 1 (
        start /wait "" "%INSTALLER%"
    )
) else (
    echo ❌ Automatic download failed. Opening Python download page in your browser...
    start https://www.python.org/downloads/
)

echo.
echo Re-checking Python setup...
py -3.11 setup_helper.py 2>nul || py -3 setup_helper.py 2>nul || python setup_helper.py 2>nul

if errorlevel 1 (
    echo.
    echo ℹ️ If Python 3.11 was just installed, please close this window and double-click setup.bat again to finish!
)

:END
echo.
pause
