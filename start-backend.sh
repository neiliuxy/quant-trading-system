#!/bin/bash
# Start QuantX Backend API Server
# Usage: ./start-backend.sh

echo -e "\033[32mStarting QuantX Backend API Server...\033[0m"
echo -e "\033[36mAPI will be available at http://127.0.0.1:8000\033[0m"
echo -e "\033[33mPress Ctrl+C to stop the server\033[0m"
echo ""

python -m uvicorn server.main:app --host 127.0.0.1 --port 8000 --reload
