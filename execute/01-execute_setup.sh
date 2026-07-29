#!/usr/bin/env bash
# execute_setup.sh — One-time: install all Python dependencies
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"

echo "============================================"
echo "  Install Python dependencies"
echo "============================================"
py -m pip install -r requirements.txt
py -m pip install -e 03-evidence-vault
py -m pip install -r 07-block-indexer/requirements.txt

echo ""
echo "=== Setup complete ==="
