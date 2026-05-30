# Stop QuantX Backend and Frontend Servers
# Usage: .\stop-servers.ps1

Write-Host ""
Write-Host "停止 QuantX 服务器..." -ForegroundColor Yellow
Write-Host ""

# Stop backend (uvicorn on port 8000)
Write-Host "停止后端 API 服务器 (端口 8000)..." -ForegroundColor Cyan
$backendProcess = Get-Process | Where-Object { $_.ProcessName -eq "python" } | Where-Object { $_.CommandLine -like "*uvicorn*" }
if ($backendProcess) {
    Stop-Process -InputObject $backendProcess -Force -ErrorAction SilentlyContinue
    Write-Host "[OK] 后端已停止" -ForegroundColor Green
} else {
    Write-Host "[--] 后端未运行" -ForegroundColor Gray
}

# Stop frontend (node/npm on port 5173)
Write-Host "停止前端开发服务器 (端口 5173)..." -ForegroundColor Cyan
$frontendProcess = Get-Process | Where-Object { $_.ProcessName -eq "node" } | Where-Object { $_.CommandLine -like "*vite*" }
if ($frontendProcess) {
    Stop-Process -InputObject $frontendProcess -Force -ErrorAction SilentlyContinue
    Write-Host "[OK] 前端已停止" -ForegroundColor Green
} else {
    Write-Host "[--] 前端未运行" -ForegroundColor Gray
}

# Alternative: Kill by port (more reliable)
Write-Host ""
Write-Host "清理端口..." -ForegroundColor Cyan

# Kill process on port 8000
try {
    $port8000 = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess
    if ($port8000) {
        Stop-Process -Id $port8000 -Force -ErrorAction SilentlyContinue
        Write-Host "[OK] 端口 8000 已释放" -ForegroundColor Green
    }
} catch {
    # Silently ignore if port is not in use
}

# Kill process on port 5173
try {
    $port5173 = Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess
    if ($port5173) {
        Stop-Process -Id $port5173 -Force -ErrorAction SilentlyContinue
        Write-Host "[OK] 端口 5173 已释放" -ForegroundColor Green
    }
} catch {
    # Silently ignore if port is not in use
}

Write-Host ""
Write-Host "所有服务器已停止。" -ForegroundColor Green
Write-Host ""

