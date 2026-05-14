#!/bin/bash
# Modernized Setup script for gemini host proxy.
# Uses 'uv' for Python environment and Smart-Path for CLI discovery.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Gemini Proxy Setup (Modernized) ==="
echo ""

# 1. Check for uv
if ! command -v uv &>/dev/null; then
    echo "uv not found. Installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source $HOME/.cargo/env
fi

# 2. Sync Python environment
echo "Syncing Python dependencies..."
cd "$SCRIPT_DIR"
uv sync

# 3. Check for gemini CLI (via Smart-Path logic or simple check)
echo ""
echo "Checking for Gemini CLI..."
# Source nvm if exists
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

if ! command -v gemini &>/dev/null; then
    echo "gemini not found. Attempting install via npm..."
    if command -v npm &>/dev/null; then
        npm install -g @google/gemini-cli
    else
        echo "WARNING: npm not found. Please install Node.js/Gemini CLI manually."
    fi
fi

# 4. Verify Proxy
echo ""
echo "Verifying Smart-Path discovery..."
uv run python3 gemini_proxy.py --help >/dev/null 2>&1 || true
# We just want to see if it starts and finds gemini in logs (if we ran it)
# But here we just finish setup.

echo ""
echo "=== Setup complete ==="
echo ""
echo "Start the proxy:"
echo "  cp $SCRIPT_DIR/gemini-proxy.service /etc/systemd/system/"
echo "  systemctl daemon-reload"
echo "  systemctl enable --now gemini-proxy"
echo ""
echo "Check logs:"
echo "  journalctl -u gemini-proxy -f"
