#!/usr/bin/env bash
# execute_dash.sh — Generate a static ledger dashboard (no server needed)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"

echo "============================================"
echo "  Generate Static Audit Dashboard"
echo "============================================"
echo ""

py 08-Dashboard/generate_report.py

echo ""
echo "Open 08-Dashboard/dashboard.html in your browser."
