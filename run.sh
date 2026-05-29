#!/bin/bash

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | xargs)
fi

cleanup() {
    echo "Cleaning up..."
    [ -n "$AGY_PROXY_PID" ] && kill "$AGY_PROXY_PID" 2>/dev/null
    exit 0
}
trap cleanup SIGINT SIGTERM

# Ensure directories exist
mkdir -p static/uploads

# Install dependencies
pip install -r requirements.txt

# Start agy host proxy (non-Docker mode)
if [ -z "$AGY_HOST_URL" ] && command -v agy &>/dev/null; then
    echo "Starting agy proxy on port 8765..."
    python3 host/agy_proxy.py &
    AGY_PROXY_PID=$!
    sleep 1
    if ! kill -0 "$AGY_PROXY_PID" 2>/dev/null; then
        echo "WARNING: agy proxy failed to start, AI features will be disabled"
    else
        export AGY_HOST_URL="http://127.0.0.1:8765"
        echo "agy proxy started (PID: $AGY_PROXY_PID)"
    fi
elif [ -n "$AGY_HOST_URL" ]; then
    echo "Using external agy host: $AGY_HOST_URL"
else
    echo "agy CLI not found — AI features will be disabled"
fi

# Seed the database
python3 seed_db.py

# Run the application
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
