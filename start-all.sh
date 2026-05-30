#!/bin/bash
# Start Both QuantX Backend and Frontend Servers
# Usage: ./start-all.sh

echo ""
echo "============================================================"
echo "          QuantX Backtest Dashboard - Start All"
echo "============================================================"
echo ""

# Check if npm is installed
if ! command -v npm &> /dev/null; then
    echo "Error: npm not found. Please install Node.js first."
    exit 1
fi

# Check if Python is installed
if ! command -v python &> /dev/null; then
    echo "Error: Python not found. Please install Python first."
    exit 1
fi

echo "Starting Backend API Server..."
echo "  - http://127.0.0.1:8000"
echo ""

# Start backend in background
python -m uvicorn server.main:app --host 127.0.0.1 --port 8000 --reload &
BACKEND_PID=$!

# Wait for backend to start
sleep 3

echo "Starting Frontend Development Server..."
echo "  - http://127.0.0.1:5173"
echo ""

# Start frontend in background
cd web
npm run dev &
FRONTEND_PID=$!

cd ..

echo ""
echo "============================================================"
echo "                    Servers Started!"
echo "============================================================"
echo "Backend:  http://127.0.0.1:8000"
echo "Frontend: http://127.0.0.1:5173"
echo ""
echo "Backend PID:  $BACKEND_PID"
echo "Frontend PID: $FRONTEND_PID"
echo ""
echo "To stop all servers, run: ./stop-servers.sh"
echo "============================================================"
echo ""

# Open browser (macOS)
if command -v open &> /dev/null; then
    sleep 2
    open "http://127.0.0.1:5173"
fi

# Open browser (Linux)
if command -v xdg-open &> /dev/null; then
    sleep 2
    xdg-open "http://127.0.0.1:5173"
fi

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID
