#!/bin/bash

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | xargs)
fi

cleanup() {
    echo "Cleaning up..."
    [ -n "$GEMINI_PROXY_PID" ] && kill "$GEMINI_PROXY_PID" 2>/dev/null
    exit 0
}
trap cleanup SIGINT SIGTERM

# Ensure directories exist
mkdir -p static/uploads

# Install dependencies
pip install -r requirements.txt

# Create gemini-bin symlink if gemini exists but symlink doesn't
if [ ! -f host/gemini-bin ] && command -v gemini &>/dev/null; then
    echo "Creating gemini symlink..."
    bash host/setup.sh
fi

# Start gemini host proxy (non-Docker mode)
if [ -z "$GEMINI_HOST_URL" ] && [ -f host/gemini-bin ]; then
    echo "Starting gemini proxy on port 8765..."
    python3 host/gemini_proxy.py &
    GEMINI_PROXY_PID=$!
    sleep 1
    if ! kill -0 "$GEMINI_PROXY_PID" 2>/dev/null; then
        echo "WARNING: gemini proxy failed to start, AI features will be disabled"
    else
        export GEMINI_HOST_URL="http://127.0.0.1:8765"
        echo "gemini proxy started (PID: $GEMINI_PROXY_PID)"
    fi
elif [ -n "$GEMINI_HOST_URL" ]; then
    echo "Using external gemini host: $GEMINI_HOST_URL"
else
    echo "gemini CLI not found — AI features will be disabled"
fi

# Seed the database
python3 seed_db.py

# Run the application
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
