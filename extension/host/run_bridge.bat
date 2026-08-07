@echo off
REM Wrapper for Browser Use native messaging host
REM Logs all output to a file for debugging

set LOG_FILE=%TEMP%\browser_use_native_host_wrapper.log
echo %DATE% %TIME% - Starting native host wrapper >> "%LOG_FILE%"
echo %DATE% %TIME% - Python: C:\Users\acer\AppData\Local\Programs\Python\Python312\python.exe >> "%LOG_FILE%"
echo %DATE% %TIME% - Script: C:\Users\acer\OneDrive - ELCOT\AUTO\extension\host\bridge.py >> "%LOG_FILE%"
echo %DATE% %TIME% - Working dir: %CD% >> "%LOG_FILE%"
echo %DATE% %TIME% - Args: %* >> "%LOG_FILE%"

"C:\Users\acer\AppData\Local\Programs\Python\Python312\python.exe" "C:\Users\acer\OneDrive - ELCOT\AUTO\extension\host\bridge.py" 2>> "%LOG_FILE%"

echo %DATE% %TIME% - Native host exited with code: %ERRORLEVEL% >> "%LOG_FILE%"