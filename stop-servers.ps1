# Stop QuantX Backend and Frontend Servers
# Usage: .\stop-servers.ps1

Write-Host "Stopping QuantX Servers..." -ForegroundColor Yellow
Write-Host ""

# Stop backend (uvicorn on port 8000)
Write-Host "Stopping backend API server (port 8000)..." -ForegroundColor Cyan
$backendProcess = Get-Process | Where-Object { $_.ProcessName -eq "python" -and $_.CommandLine -like "*uvicorn*server.main*" }
if ($backendProcess) {
    Stop-Process -InputObject $backendProcess -Force -ErrorAction SilentlyContinue
    Write-Host "✓ Backend stopped" -ForegroundColor Green
} else {
    Write-Host "✗ Backend not running" -ForegroundColor Gray
}

# Stop frontend (vite on port 5173)
Write-Host "Stopping frontend dev server (port 5173)..." -ForegroundColor Cyan
$frontendProcess = Get-Process | Where-Object { $_.ProcessName -eq "node" -and $_.CommandLine -like "*vite*" }
if ($frontendProcess) {
    Stop-Process -InputObject $frontendProcess -Force -ErrorAction SilentlyContinue
    Write-Host "✓ Frontend stopped" -ForegroundColor Green
} else {
    Write-Host "✗ Frontend not running" -ForegroundColor Gray
}

# Alternative: Kill by port (more reliable)
Write-Host ""
Write-Host "Cleaning up ports..." -ForegroundColor Cyan

# Kill process on port 8000
$port8000 = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess
if ($port8000) {
    Stop-Process -Id $port8000 -Force -ErrorAction SilentlyContinue
    Write-Host "✓ Port 8000 released" -ForegroundColor Green
}

# Kill process on port 5173
$port5173 = Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess
if ($port5173) {
    Stop-Process -Id $port5173 -Force -ErrorAction SilentlyContinue
    Write-Host "✓ Port 5173 released" -ForegroundColor Green
}

Write-Host ""
Write-Host "All servers stopped." -ForegroundColor Green
