#!/bin/bash
# Start QuantX Frontend Development Server
# Usage: ./start-frontend.sh

echo -e "\033[32mStarting QuantX Frontend Development Server...\033[0m"
echo -e "\033[36mFrontend will be available at http://127.0.0.1:5173\033[0m"
echo -e "\033[33mPress Ctrl+C to stop the server\033[0m"
echo ""

cd web
npm run dev
