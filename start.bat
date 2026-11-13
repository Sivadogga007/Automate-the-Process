@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto launch
where py >nul 2>nul
if not errorlevel 1 (
    py -3 -m venv .venv
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo Install Python 3.11 or newer from python.org, then try again.
        goto failed
    )
    python -m venv .venv
)
if errorlevel 1 goto failed
:launch
".venv\Scripts\python.exe" launch.py %*
if errorlevel 1 goto failed
pause
exit /b 0
:failed
echo Launcher stopped. Read the error above.
pause
exit /b 1
