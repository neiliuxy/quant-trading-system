#!/bin/bash
# Stop QuantX Backend and Frontend Servers
# Usage: ./stop-servers.sh

PID_DIR="${XDG_RUNTIME_DIR:-/tmp}/quantx"
PID_FILE_BACKEND="${PID_DIR}/backend.pid"
PID_FILE_FRONTEND="${PID_DIR}/frontend.pid"

stop_process() {
    local label="$1"
    local pid_file="$2"
    if [ -f "$pid_file" ]; then
        local pid
        pid="$(cat "$pid_file")"
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            echo "Stopping $label (PID $pid)..."
            kill -TERM "$pid"
            sleep 1
            if kill -0 "$pid" 2>/dev/null; then
                kill -KILL "$pid" 2>/dev/null
            fi
            echo "$label stopped"
        else
            echo "$label not running (stale PID file)"
        fi
        rm -f "$pid_file"
    else
        echo "$label PID file not found — is it running?"
    fi
}

echo "Stopping QuantX Servers..."
echo ""

stop_process "Backend" "$PID_FILE_BACKEND"
stop_process "Frontend" "$PID_FILE_FRONTEND"

echo ""
echo "All servers stopped."
echo ""
