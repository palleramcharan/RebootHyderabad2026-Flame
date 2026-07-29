#!/usr/bin/env bash
# Start the Fabric network
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NETWORK_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Starting Fabric network ==="
echo "Topology: 1 Org, 1 Peer, 1 Orderer (RAFT), 1 CA, 1 CouchDB"
echo "Channel: auditchannel"

cd "${NETWORK_DIR}"
docker compose up -d

echo "=== Network started ==="
echo "Containers:"
docker compose ps

echo ""
echo "  CA:            ca-org1 (7054)"
echo "  Orderer:       orderer0.example.com (7050, RAFT)"
echo "  Peer:          peer0.org1.example.com (7051/7052)"
echo "  CouchDB:       couchdb0 (5984)"
echo "  Fabric Adapter: fabric-adapter (8080)"
echo "  CLI:           cli"
echo ""
echo "Run ./create-channel.sh to create auditchannel"
echo ""
echo "For split compose: docker compose -f docker-compose.fabric.yml -f docker-compose.app.yml up -d"
echo "For dev tools:     docker compose -f docker-compose.fabric.yml -f docker-compose.app.yml -f docker-compose.dev.yml up -d"
