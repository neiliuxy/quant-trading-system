# Start QuantX Backend API Server
# Usage: .\start-backend.ps1

Write-Host "Starting QuantX Backend API Server..." -ForegroundColor Green
Write-Host "API will be available at http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

python -m uvicorn server.main:app --host 127.0.0.1 --port 8000 --reload
