#!/usr/bin/env bash
# Full network teardown + crypto/block cleanup
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NETWORK_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Tearing down Fabric network ==="
cd "${NETWORK_DIR}"

docker compose down --volumes --remove-orphans

echo "=== Cleaning generated artifacts ==="
rm -rf organizations/
rm -f channel-artifacts/genesis.block
rm -f channel-artifacts/auditchannel.tx
rm -f channel-artifacts/Org1MSPanchors.tx

echo "=== Cleanup complete ==="
echo "Run ./generate.sh then ./start-network.sh to rebuild"
