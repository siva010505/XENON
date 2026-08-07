@echo off
title Xenon 1-Click Automated Setup
cd /d "%~dp0"

echo ========================================================
echo               XENON AUTOMATED SETUP
echo ========================================================
echo.

:RUN_SETUP
:: Prefer Python 3.12 then 3.11 (3.14 has incompatible browser-use package)

:: 1. Try known direct paths for Python 3.12 / 3.11 (most reliable)
if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
    "%LocalAppData%\Programs\Python\Python312\python.exe" setup_helper.py
    goto :END
)
if exist "%LocalAppData%\Programs\Python\Python311\python.exe" (
    "%LocalAppData%\Programs\Python\Python311\python.exe" setup_helper.py
    goto :END
)
if exist "C:\Program Files\Python312\python.exe" (
    "C:\Program Files\Python312\python.exe" setup_helper.py
    goto :END
)
if exist "C:\Program Files\Python311\python.exe" (
    "C:\Program Files\Python311\python.exe" setup_helper.py
    goto :END
)
if exist "C:\Python312\python.exe" (
    "C:\Python312\python.exe" setup_helper.py
    goto :END
)
if exist "C:\Python311\python.exe" (
    "C:\Python311\python.exe" setup_helper.py
    goto :END
)

:: 2. Try py launcher with specific versions
py -3.12 --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    py -3.12 setup_helper.py
    goto :END
)

py -3.11 --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    py -3.11 setup_helper.py
    goto :END
)

:: 3. Try default python only if version is exactly 3.11 or 3.12
python -c "import sys; sys.exit(0 if sys.version_info[:2] in [(3,11),(3,12)] else 1)" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    python setup_helper.py
    goto :END
)

:: 4. If no compatible Python found, download Python 3.11 automatically
echo.
echo Python 3.11 or 3.12 is required but was not found on your system.
echo Automatically downloading official Python 3.11 installer from python.org...
echo.

set "INSTALLER=%TEMP%\python-3.11.9-amd64.exe"

curl.exe -sSL -o "%INSTALLER%" "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
if not exist "%INSTALLER%" (
    powershell -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object System.Net.WebClient).Headers.Add('User-Agent', 'Mozilla/5.0'); (New-Object System.Net.WebClient).DownloadFile('https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe', '%INSTALLER%')"
)

if exist "%INSTALLER%" (
    echo Launching Python 3.11 Installer...
    echo In the installer window, please click "Install Now"!
    echo.
    start /wait "" "%INSTALLER%" /passive PrependPath=1
    if errorlevel 1 (
        start /wait "" "%INSTALLER%"
    )
    del "%INSTALLER%" >nul 2>&1
    echo.
    echo Python installation complete! Running Xenon setup...
    goto :RUN_SETUP
) else (
    echo Automatic download failed. Opening Python download page in your browser...
    start https://www.python.org/downloads/
)

:END
echo.
pause
