@echo off
echo =========================================
echo Starting Xenon Backend Server...
echo =========================================
echo.

:: Get the directory of this batch file
set "DIR=%~dp0"
cd /d "%DIR%backend"

:: Check if the virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found in %DIR%backend\venv
    echo Please make sure the setup is complete.
    pause
    exit /b
)

:: Activate and run the server
call venv\Scripts\activate.bat
echo [INFO] Environment activated. Starting Uvicorn with auto-reload...
uvicorn server:app --host 127.0.0.1 --port 8000 --reload

pause
