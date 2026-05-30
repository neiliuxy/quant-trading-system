#!/bin/bash
# Start Both QuantX Backend and Frontend Servers
# Usage: ./start-all.sh

echo -e "\033[36m╔════════════════════════════════════════════════════════════╗\033[0m"
echo -e "\033[36m║         QuantX Backtest Dashboard - Start All             ║\033[0m"
echo -e "\033[36m╚════════════════════════════════════════════════════════════╝\033[0m"
echo ""

# Check if npm is installed
if ! command -v npm &> /dev/null; then
    echo -e "\033[31m✗ npm not found. Please install Node.js first.\033[0m"
    exit 1
fi

# Check if Python is installed
if ! command -v python &> /dev/null; then
    echo -e "\033[31m✗ Python not found. Please install Python first.\033[0m"
    exit 1
fi

echo -e "\033[32mStarting Backend API Server...\033[0m"
echo -e "\033[36m  → http://127.0.0.1:8000\033[0m"
echo ""

# Start backend in background
python -m uvicorn server.main:app --host 127.0.0.1 --port 8000 --reload &
BACKEND_PID=$!

# Wait a moment for backend to start
sleep 2

echo -e "\033[32mStarting Frontend Development Server...\033[0m"
echo -e "\033[36m  → http://127.0.0.1:5173\033[0m"
echo ""

# Start frontend in background
cd web
npm run dev &
FRONTEND_PID=$!

cd ..

echo ""
echo -e "\033[32m╔════════════════════════════════════════════════════════════╗\033[0m"
echo -e "\033[32m║                    Servers Started!                        ║\033[0m"
echo -e "\033[32m╠════════════════════════════════════════════════════════════╣\033[0m"
echo -e "\033[32m║  Backend:  http://127.0.0.1:8000                          ║\033[0m"
echo -e "\033[32m║  Frontend: http://127.0.0.1:5173                          ║\033[0m"
echo -e "\033[32m║                                                            ║\033[0m"
echo -e "\033[32m║  Backend PID:  $BACKEND_PID                                    ║\033[0m"
echo -e "\033[32m║  Frontend PID: $FRONTEND_PID                                    ║\033[0m"
echo -e "\033[32m║                                                            ║\033[0m"
echo -e "\033[32m║  To stop all servers, run: ./stop-servers.sh              ║\033[0m"
echo -e "\033[32m╚════════════════════════════════════════════════════════════╝\033[0m"
echo ""

# Open browser (macOS)
if command -v open &> /dev/null; then
    sleep 3
    open "http://127.0.0.1:5173"
fi

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID
