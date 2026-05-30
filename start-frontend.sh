#!/bin/bash
# Start QuantX Frontend Development Server
# Usage: ./start-frontend.sh

echo ""
echo "Starting QuantX Frontend Development Server..."
echo "Frontend will be available at http://127.0.0.1:5173"
echo "Press Ctrl+C to stop the server"
echo ""

cd web
npm run dev
