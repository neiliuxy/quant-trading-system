# Start Both QuantX Backend and Frontend Servers
# Usage: .\start-all.ps1

Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║         QuantX Backtest Dashboard - Start All             ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Check if npm is installed
$npmCheck = npm --version 2>$null
if (-not $npmCheck) {
    Write-Host "✗ npm not found. Please install Node.js first." -ForegroundColor Red
    exit 1
}

# Check if Python is installed
$pythonCheck = python --version 2>$null
if (-not $pythonCheck) {
    Write-Host "✗ Python not found. Please install Python first." -ForegroundColor Red
    exit 1
}

Write-Host "Starting Backend API Server..." -ForegroundColor Green
Write-Host "  → http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host ""

# Start backend in a new window
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot'; python -m uvicorn server.main:app --host 127.0.0.1 --port 8000 --reload" -WindowStyle Normal

# Wait a moment for backend to start
Start-Sleep -Seconds 2

Write-Host "Starting Frontend Development Server..." -ForegroundColor Green
Write-Host "  → http://127.0.0.1:5173" -ForegroundColor Cyan
Write-Host ""

# Start frontend in a new window
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot/web'; npm run dev" -WindowStyle Normal

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║                    Servers Started!                        ║" -ForegroundColor Green
Write-Host "╠════════════════════════════════════════════════════════════╣" -ForegroundColor Green
Write-Host "║  Backend:  http://127.0.0.1:8000                          ║" -ForegroundColor Green
Write-Host "║  Frontend: http://127.0.0.1:5173                          ║" -ForegroundColor Green
Write-Host "║                                                            ║" -ForegroundColor Green
Write-Host "║  To stop all servers, run: .\stop-servers.ps1             ║" -ForegroundColor Green
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "Opening dashboard in browser..." -ForegroundColor Cyan
Start-Sleep -Seconds 3
Start-Process "http://127.0.0.1:5173"
