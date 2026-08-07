@echo off
title Xenon 1-Click Automated Setup
cd /d "%~dp0"

:: Try Windows Python launcher py -3.11 first
py -3.11 --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    py -3.11 setup_helper.py
    pause
    exit /b
)

:: Try Windows Python launcher py -3 next
py -3 --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    py -3 setup_helper.py
    pause
    exit /b
)

:: Try python next if version >= 3.11
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    python setup_helper.py
    pause
    exit /b
)

echo ========================================================
echo ⚠️ Python 3.11+ is required but was not found on your system.
echo Automatically downloading official Python 3.11 installer...
echo ========================================================
echo.

powershell -Command "
$url = 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe'
$output = \"$env:TEMP\python-3.11.9-amd64.exe\"
Write-Host 'Downloading Python 3.11 installer from python.org...'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
(New-Object System.Net.WebClient).DownloadFile($url, $output)
Write-Host 'Installing Python 3.11 automatically (Adding to PATH)...'
Start-Process -FilePath $output -ArgumentList '/passive PrependPath=1' -Wait
"

echo.
echo Setup complete! Running Xenon setup...
py -3.11 setup_helper.py 2>nul || py -3 setup_helper.py 2>nul || python setup_helper.py
pause
