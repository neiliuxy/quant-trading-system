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

Write-Host "Starting Backend API Server..." -ForegroundColor Green
Write-Host "  - http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host ""

# Start backend in background (no new window)
$backendProcess = Start-Process python -ArgumentList "-m", "uvicorn", "server.main:app", "--host", "127.0.0.1", "--port", "8000", "--reload" -PassThru -NoNewWindow -RedirectStandardOutput "$PSScriptRoot\logs\backend.log" -RedirectStandardError "$PSScriptRoot\logs\backend-error.log"

# Create logs directory if it doesn't exist
if (!(Test-Path "$PSScriptRoot\logs")) {
    New-Item -ItemType Directory -Path "$PSScriptRoot\logs" | Out-Null
}

# Wait for backend to start
Start-Sleep -Seconds 3

Write-Host "Starting Frontend Development Server..." -ForegroundColor Green
Write-Host "  - http://127.0.0.1:5173" -ForegroundColor Cyan
Write-Host ""

# Start frontend in background (no new window)
$frontendProcess = Start-Process npm -ArgumentList "run", "dev" -PassThru -NoNewWindow -WorkingDirectory "$PSScriptRoot\web" -RedirectStandardOutput "$PSScriptRoot\logs\frontend.log" -RedirectStandardError "$PSScriptRoot\logs\frontend-error.log"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "                    Servers Started!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host "Backend:  http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "Frontend: http://127.0.0.1:5173" -ForegroundColor Green
Write-Host ""
Write-Host "Backend PID:  $($backendProcess.Id)" -ForegroundColor Cyan
Write-Host "Frontend PID: $($frontendProcess.Id)" -ForegroundColor Cyan
Write-Host ""
Write-Host "Logs:" -ForegroundColor Cyan
Write-Host "  Backend:  $PSScriptRoot\logs\backend.log" -ForegroundColor Cyan
Write-Host "  Frontend: $PSScriptRoot\logs\frontend.log" -ForegroundColor Cyan
Write-Host ""
Write-Host "To stop all servers, run: .\stop-servers.ps1" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""

# Wait a bit for servers to be ready
Start-Sleep -Seconds 3

# Open browser
Write-Host "Opening dashboard in browser..." -ForegroundColor Cyan
Start-Process "http://127.0.0.1:5173"

Write-Host "Dashboard opened in browser." -ForegroundColor Cyan
Write-Host ""

