#!/bin/bash
# Stop QuantX Backend and Frontend Servers
# Usage: ./stop-servers.sh

echo ""
echo "Stopping QuantX Servers..."
echo ""

# Stop backend (uvicorn on port 8000)
echo "Stopping backend API server (port 8000)..."
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    kill -9 $(lsof -t -i:8000) 2>/dev/null
    echo "Backend stopped"
else
    echo "Backend not running"
fi

# Stop frontend (vite on port 5173)
echo "Stopping frontend dev server (port 5173)..."
if lsof -Pi :5173 -sTCP:LISTEN -t >/dev/null 2>&1; then
    kill -9 $(lsof -t -i:5173) 2>/dev/null
    echo "Frontend stopped"
else
    echo "Frontend not running"
fi

echo ""
echo "All servers stopped."
echo ""
