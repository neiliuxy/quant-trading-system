# Start Both QuantX Backend and Frontend Servers
# Usage: .\start-all.ps1

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "          QuantX 回测仪表板 - 启动所有服务" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Check if npm is installed
try {
    $npmVersion = npm --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "错误: 未找到 npm。请先安装 Node.js。" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "错误: 未找到 npm。请先安装 Node.js。" -ForegroundColor Red
    exit 1
}

# Check if Python is installed
try {
    $pythonVersion = python --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "错误: 未找到 Python。请先安装 Python。" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "错误: 未找到 Python。请先安装 Python。" -ForegroundColor Red
    exit 1
}

Write-Host "在新窗口中启动后端 API 服务器..." -ForegroundColor Green
Write-Host "  - http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host ""

# Start backend in a new PowerShell window
$backendScript = @"
Set-Location '$PSScriptRoot'
python -m uvicorn server.main:app --host 127.0.0.1 --port 8000 --reload
"@
Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendScript -WindowStyle Normal

# Wait for backend to start
Start-Sleep -Seconds 3

Write-Host "在新窗口中启动前端开发服务器..." -ForegroundColor Green
Write-Host "  - http://127.0.0.1:5173" -ForegroundColor Cyan
Write-Host ""

# Start frontend in a new PowerShell window
$frontendScript = @"
Set-Location '$PSScriptRoot\web'
npm run dev
"@
Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendScript -WindowStyle Normal

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "                    服务器已启动!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host "后端:  http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "前端: http://127.0.0.1:5173" -ForegroundColor Green
Write-Host ""
Write-Host "要停止所有服务器，请运行: .\stop-servers.ps1" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "在浏览器中打开仪表板..." -ForegroundColor Cyan
Start-Sleep -Seconds 3
Start-Process "http://127.0.0.1:5173"

Write-Host ""
Write-Host "仪表板已在浏览器中打开。" -ForegroundColor Cyan
Write-Host ""
