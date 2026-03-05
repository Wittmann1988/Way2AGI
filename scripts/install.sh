#!/usr/bin/env bash
set -euo pipefail

# Way2AGI Installation Script
# Works on: Linux, macOS, Windows (WSL2), Android (Termux)

echo "=== Way2AGI Installer ==="
echo ""

# Detect platform
PLATFORM="unknown"
if [ -d "/data/data/com.termux" ]; then
    PLATFORM="termux"
elif grep -qi "microsoft" /proc/version 2>/dev/null; then
    PLATFORM="wsl2"
elif [ "$(uname)" = "Darwin" ]; then
    PLATFORM="macos"
elif [ "$(uname)" = "Linux" ]; then
    PLATFORM="linux"
fi
echo "[*] Platform: $PLATFORM"

# Check Node.js
if ! command -v node &>/dev/null; then
    echo "[!] Node.js not found. Installing..."
    case $PLATFORM in
        termux) pkg install -y nodejs-lts ;;
        macos) brew install node ;;
        *) echo "Please install Node.js 22+ manually"; exit 1 ;;
    esac
fi
echo "[*] Node.js: $(node --version)"

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "[!] Python3 not found. Installing..."
    case $PLATFORM in
        termux) pkg install -y python ;;
        macos) brew install python ;;
        *) echo "Please install Python 3.11+ manually"; exit 1 ;;
    esac
fi
echo "[*] Python: $(python3 --version)"

# Check pnpm
if ! command -v pnpm &>/dev/null; then
    echo "[*] Installing pnpm..."
    npm install -g pnpm
fi
echo "[*] pnpm: $(pnpm --version)"

# Install TypeScript dependencies
echo ""
echo "[*] Installing TypeScript dependencies..."
pnpm install

# Build TypeScript
echo "[*] Building TypeScript modules..."
pnpm build

# Install Python dependencies
echo ""
echo "[*] Installing Python memory server..."
cd memory
pip install -e ".[full]" 2>/dev/null || pip install -e "."
cd ..

echo ""
echo "=== Installation Complete ==="
echo ""
echo "Next steps:"
echo "  1. Set TELEGRAM_BOT_TOKEN in your environment"
echo "  2. Run: python memory/src/server.py &"
echo "  3. Run: pnpm start"
echo "  4. Or use: docker compose up"
echo ""
echo "Health check: curl http://localhost:18789/health"
