#!/bin/bash
# Setup script for AGY host proxy.
# Uses 'uv' for Python environment and Smart-Path for CLI discovery.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== AGY Proxy Setup ==="
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

# 3. Check for agy CLI
echo ""
echo "Checking for AGY CLI..."
if ! command -v agy &>/dev/null; then
    echo "agy not found. Attempting install..."
    curl -fsSL https://antigravity.google/cli/install.sh | bash
    # Source shell profile to pick up new PATH
    [ -f "$HOME/.bashrc" ] && source "$HOME/.bashrc" 2>/dev/null || true
    [ -f "$HOME/.zshrc" ] && source "$HOME/.zshrc" 2>/dev/null || true
fi

if command -v agy &>/dev/null; then
    echo "AGY CLI found: $(which agy)"
else
    echo "WARNING: agy CLI not found. Please install manually:"
    echo "  curl -fsSL https://antigravity.google/cli/install.sh | bash"
fi

# 4. Verify Proxy
echo ""
echo "Verifying Smart-Path discovery..."
uv run python3 agy_proxy.py --help >/dev/null 2>&1 || true

echo ""
echo "=== Setup complete ==="
echo ""
echo "Start the proxy:"
echo "  cp $SCRIPT_DIR/agy-proxy.service /etc/systemd/system/"
echo "  systemctl daemon-reload"
echo "  systemctl enable --now agy-proxy"
echo ""
echo "Check logs:"
echo "  journalctl -u agy-proxy -f"
