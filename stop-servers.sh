#!/bin/bash
# Stop QuantX Backend and Frontend Servers
# Usage: ./stop-servers.sh

echo -e "\033[33mStopping QuantX Servers...\033[0m"
echo ""

# Stop backend (uvicorn on port 8000)
echo -e "\033[36mStopping backend API server (port 8000)...\033[0m"
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    kill -9 $(lsof -t -i:8000) 2>/dev/null
    echo -e "\033[32m✓ Backend stopped\033[0m"
else
    echo -e "\033[90m✗ Backend not running\033[0m"
fi

# Stop frontend (vite on port 5173)
echo -e "\033[36mStopping frontend dev server (port 5173)...\033[0m"
if lsof -Pi :5173 -sTCP:LISTEN -t >/dev/null 2>&1; then
    kill -9 $(lsof -t -i:5173) 2>/dev/null
    echo -e "\033[32m✓ Frontend stopped\033[0m"
else
    echo -e "\033[90m✗ Frontend not running\033[0m"
fi

echo ""
echo -e "\033[32mAll servers stopped.\033[0m"
