# Start QuantX Frontend Development Server
# Usage: .\start-frontend.ps1

Write-Host ""
Write-Host "Starting QuantX Frontend Development Server..." -ForegroundColor Green
Write-Host "Frontend will be available at http://127.0.0.1:5173" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

Set-Location web
npm run dev
