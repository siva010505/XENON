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

powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $out = '$env:TEMP\python-3.11.9-amd64.exe'; (New-Object System.Net.WebClient).DownloadFile('https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe', $out); Start-Process -FilePath $out -ArgumentList '/passive PrependPath=1' -Wait"

echo.
echo Python installation complete! Running Xenon setup...
py -3.11 setup_helper.py 2>nul || py -3 setup_helper.py 2>nul || python setup_helper.py

:END
echo.
pause
