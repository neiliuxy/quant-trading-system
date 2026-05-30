#!/bin/bash
# Start QuantX Backend API Server
# Usage: ./start-backend.sh

echo ""
echo "Starting QuantX Backend API Server..."
echo "API will be available at http://127.0.0.1:8000"
echo "Press Ctrl+C to stop the server"
echo ""

python -m uvicorn server.main:app --host 127.0.0.1 --port 8000 --reload
