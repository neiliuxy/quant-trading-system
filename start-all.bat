@echo off
REM Start Both QuantX Backend and Frontend Servers
REM Usage: start-all.bat
REM Opens two separate command windows for backend and frontend

cls
echo.
echo ============================================================
echo          QuantX Backtest Dashboard - Start All
echo ============================================================
echo.

REM Check if npm is installed
npm --version >nul 2>&1
if errorlevel 1 (
    echo Error: npm not found. Please install Node.js first.
    pause
    exit /b 1
)

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python not found. Please install Python first.
    pause
    exit /b 1
)

echo Starting Backend API Server in new window...
echo   - http://127.0.0.1:8000
echo.

REM Start backend in a new window
start "QuantX Backend" cmd /k "python -m uvicorn server.main:app --host 127.0.0.1 --port 8000 --reload"

REM Wait for backend to start
timeout /t 3 /nobreak

echo Starting Frontend Development Server in new window...
echo   - http://127.0.0.1:5173
echo.

REM Start frontend in a new window
start "QuantX Frontend" cmd /k "cd /d %~dp0web && npm run dev"

echo.
echo ============================================================
echo                    Servers Started!
echo ============================================================
echo Backend:  http://127.0.0.1:8000
echo Frontend: http://127.0.0.1:5173
echo.
echo To stop all servers, run: stop-servers.bat
echo ============================================================
echo.

REM Wait and open browser
timeout /t 3 /nobreak
start http://127.0.0.1:5173

echo Dashboard opened in browser.
echo.
