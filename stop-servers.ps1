# Stop QuantX Backend and Frontend Servers
# Usage: .\stop-servers.ps1

Write-Host ""
Write-Host "Stopping QuantX Servers..." -ForegroundColor Yellow
Write-Host ""

# Stop backend (uvicorn on port 8000)
Write-Host "Stopping backend API server (port 8000)..." -ForegroundColor Cyan
$backendProcess = Get-Process | Where-Object { $_.ProcessName -eq "python" } | Where-Object { $_.CommandLine -like "*uvicorn*" }
if ($backendProcess) {
    Stop-Process -InputObject $backendProcess -Force -ErrorAction SilentlyContinue
    Write-Host "✓ Backend stopped" -ForegroundColor Green
} else {
    Write-Host "✗ Backend not running" -ForegroundColor Gray
}

# Stop frontend (node/npm on port 5173)
Write-Host "Stopping frontend dev server (port 5173)..." -ForegroundColor Cyan
$frontendProcess = Get-Process | Where-Object { $_.ProcessName -eq "node" } | Where-Object { $_.CommandLine -like "*vite*" }
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
try {
    $port8000 = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess
    if ($port8000) {
        Stop-Process -Id $port8000 -Force -ErrorAction SilentlyContinue
        Write-Host "✓ Port 8000 released" -ForegroundColor Green
    }
} catch {
    # Silently ignore if port is not in use
}

# Kill process on port 5173
try {
    $port5173 = Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess
    if ($port5173) {
        Stop-Process -Id $port5173 -Force -ErrorAction SilentlyContinue
        Write-Host "✓ Port 5173 released" -ForegroundColor Green
    }
} catch {
    # Silently ignore if port is not in use
}

Write-Host ""
Write-Host "All servers stopped." -ForegroundColor Green
Write-Host ""
