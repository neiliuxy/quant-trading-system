# Start QuantX Backend API Server
# Usage: .\start-backend.ps1

Write-Host ""
Write-Host "启动 QuantX 后端 API 服务器..." -ForegroundColor Green
Write-Host "API 将在 http://127.0.0.1:8000 上可用" -ForegroundColor Cyan
Write-Host "按 Ctrl+C 停止服务器" -ForegroundColor Yellow
Write-Host ""

python -m uvicorn server.main:app --host 127.0.0.1 --port 8000 --reload
