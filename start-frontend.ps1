# Start QuantX Frontend Development Server
# Usage: .\start-frontend.ps1

Write-Host ""
Write-Host "启动 QuantX 前端开发服务器..." -ForegroundColor Green
Write-Host "前端将在 http://127.0.0.1:5173 上可用" -ForegroundColor Cyan
Write-Host "按 Ctrl+C 停止服务器" -ForegroundColor Yellow
Write-Host ""

Set-Location web
npm run dev
