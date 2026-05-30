@echo off
REM Stop QuantX Backend and Frontend Servers
REM Usage: stop-servers.bat

echo.
echo Stopping QuantX Servers...
echo.

REM Kill process on port 8000 (backend)
echo Stopping backend API server (port 8000)...
for /f "tokens=5" %%a in ('netstat -aon ^| find ":8000" ^| find "LISTENING"') do taskkill /pid %%a /f 2>nul
if %errorlevel% equ 0 (
    echo Backend stopped
) else (
    echo Backend not running
)

REM Kill process on port 5173 (frontend)
echo Stopping frontend dev server (port 5173)...
for /f "tokens=5" %%a in ('netstat -aon ^| find ":5173" ^| find "LISTENING"') do taskkill /pid %%a /f 2>nul
if %errorlevel% equ 0 (
    echo Frontend stopped
) else (
    echo Frontend not running
)

echo.
echo All servers stopped.
echo.
