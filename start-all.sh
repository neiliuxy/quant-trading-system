#!/bin/bash
# Start Both QuantX Backend and Frontend Servers
# Usage: ./start-all.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_DIR="${XDG_RUNTIME_DIR:-/tmp}/quantx"
PID_FILE_BACKEND="${PID_DIR}/backend.pid"
PID_FILE_FRONTEND="${PID_DIR}/frontend.pid"

mkdir -p "$PID_DIR"

cleanup() {
    if [ -f "$PID_FILE_BACKEND" ]; then
        kill -0 "$(cat "$PID_FILE_BACKEND")" 2>/dev/null && kill -TERM "$(cat "$PID_FILE_BACKEND")"
    fi
    if [ -f "$PID_FILE_FRONTEND" ]; then
        kill -0 "$(cat "$PID_FILE_FRONTEND")" 2>/dev/null && kill -TERM "$(cat "$PID_FILE_FRONTEND")"
    fi
    rm -f "$PID_FILE_BACKEND" "$PID_FILE_FRONTEND"
}
trap cleanup EXIT

if ! command -v npm &> /dev/null; then
    echo "Error: npm not found."
    exit 1
fi
if ! command -v python &> /dev/null; then
    echo "Error: python not found."
    exit 1
fi

echo "Starting Backend API Server (port 8000)..."
python -m uvicorn server.main:app --host 127.0.0.1 --port 8000 --reload &
BACKEND_PID=$!
echo $BACKEND_PID > "$PID_FILE_BACKEND"
echo "Backend PID: $BACKEND_PID"

sleep 2

echo "Starting Frontend Dev Server (port 5173)..."
(cd "$SCRIPT_DIR/web" && npm run dev) &
FRONTEND_PID=$!
echo $FRONTEND_PID > "$PID_FILE_FRONTEND"
echo "Frontend PID: $FRONTEND_PID"

sleep 2

BROWSER_URL="http://127.0.0.1:5173"
if command -v open &> /dev/null; then
    open "$BROWSER_URL"
elif command -v xdg-open &> /dev/null; then
    xdg-open "$BROWSER_URL"
fi

echo ""
echo "Backend:  http://127.0.0.1:8000"
echo "Frontend: http://127.0.0.1:5173"
echo "Run ./stop-servers.sh to stop all servers."
echo ""

wait $BACKEND_PID $FRONTEND_PID
