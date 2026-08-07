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

:: 4. If Python 3.11+ not found, download & install automatically
echo ⚠️ Python 3.11+ was not found on your system.
echo Downloading official Python 3.11 installer from python.org...
echo.

set INSTALLER=%TEMP%\python-3.11.9-amd64.exe

curl.exe -sSL -o "%INSTALLER%" "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
if not exist "%INSTALLER%" (
    powershell -Command "(New-Object System.Net.WebClient).Headers.Add('User-Agent', 'Mozilla/5.0'); (New-Object System.Net.WebClient).DownloadFile('https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe', '%INSTALLER%')"
)

if exist "%INSTALLER%" (
    echo Installing Python 3.11 automatically (Adding to PATH)...
    "%INSTALLER%" /passive PrependPath=1
    del "%INSTALLER%" >nul 2>&1
) else (
    echo ❌ Automatic download failed. Please download Python 3.11 manually from https://www.python.org/downloads/
    pause
    exit /b
)

echo.
echo Python installation complete! Running Xenon setup...
py -3.11 setup_helper.py 2>nul || py -3 setup_helper.py 2>nul || python setup_helper.py

:END
echo.
pause
