# Start Both QuantX Backend and Frontend Servers
# Usage: .\start-all.ps1

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "          QuantX Backtest Dashboard - Start All" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Check if npm is installed
npm --version >$null 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: npm not found. Please install Node.js first." -ForegroundColor Red
    exit 1
}

# Check if Python is installed
python --version >$null 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Python not found. Please install Python first." -ForegroundColor Red
    exit 1
}

Write-Host "Starting Backend API Server in new window..." -ForegroundColor Green
Write-Host "  - http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host ""

# Start backend in a new PowerShell window
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot'; python -m uvicorn server.main:app --host 127.0.0.1 --port 8000 --reload"

# Wait for backend to start
Start-Sleep -Seconds 3

Write-Host "Starting Frontend Development Server in new window..." -ForegroundColor Green
Write-Host "  - http://127.0.0.1:5173" -ForegroundColor Cyan
Write-Host ""

# Start frontend in a new PowerShell window
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\web'; npm run dev"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "                    Servers Started!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host "Backend:  http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "Frontend: http://127.0.0.1:5173" -ForegroundColor Green
Write-Host ""
Write-Host "To stop all servers, run: .\stop-servers.ps1" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""

# Wait and open browser
Start-Sleep -Seconds 3
Start-Process "http://127.0.0.1:5173"

Write-Host "Dashboard opened in browser." -ForegroundColor Cyan
Write-Host ""
