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

# Create logs directory if it doesn't exist
if (!(Test-Path "$PSScriptRoot\logs")) {
    New-Item -ItemType Directory -Path "$PSScriptRoot\logs" | Out-Null
}

Write-Host "Starting Backend API Server (minimized window)..." -ForegroundColor Green
Write-Host "  - http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host ""

# Start backend in its OWN PowerShell window — completely isolated from this terminal
$backendProcess = Start-Process powershell `
    -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot'; python -m uvicorn server.main:app --host 127.0.0.1 --port 8000 --reload" `
    -PassThru -WindowStyle Minimized

# Wait for backend to start
Start-Sleep -Seconds 3

Write-Host "Starting Frontend Development Server (minimized window)..." -ForegroundColor Green
Write-Host "  - http://127.0.0.1:5173" -ForegroundColor Cyan
Write-Host ""

# Start frontend in its OWN cmd window — completely isolated from this terminal
$frontendProcess = Start-Process cmd `
    -ArgumentList "/k", "title QuantX Frontend && cd /d `"$PSScriptRoot\web`" && npm run dev" `
    -PassThru -WindowStyle Minimized

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
Write-Host "Each server runs in its own minimized window (check taskbar)." -ForegroundColor Cyan
Write-Host "Close the minimized windows or run .\stop-servers.ps1 to stop." -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""

# Wait a bit for servers to be ready
Start-Sleep -Seconds 3

# Open browser
Write-Host "Opening dashboard in browser..." -ForegroundColor Cyan
Start-Process "http://127.0.0.1:5173"

Write-Host "Dashboard opened in browser." -ForegroundColor Cyan
Write-Host ""
