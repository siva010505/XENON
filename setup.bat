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

:: Fallback to default python
python setup_helper.py
pause
