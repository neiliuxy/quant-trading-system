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
            # Kill entire process group so child processes (uvicorn worker, node) also die
            kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null
            sleep 1
            kill -KILL -- "-$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null || true
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

# Port-based cleanup: kill anything still holding the ports regardless of PID files
_killed_any=0
for pid in $(lsof -ti :8000 2>/dev/null); do
    kill -KILL "$pid" 2>/dev/null && _killed_any=1
done
for port in 5173 5174 5175 5176 5177 5178 5179 5180; do
    for pid in $(lsof -ti :"$port" 2>/dev/null); do
        kill -KILL "$pid" 2>/dev/null && _killed_any=1
    done
done
[ "$_killed_any" -eq 1 ] && echo "Cleaned up remaining port-holding processes."

echo ""
echo "All servers stopped."
echo ""
