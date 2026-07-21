@echo off
set DIR=%~dp0
"%DIR%backend\venv\Scripts\python.exe" -u "%DIR%xenon_native_host.py"
