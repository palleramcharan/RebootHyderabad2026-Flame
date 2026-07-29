#!/bin/bash
# CouchDB Recovery Script
# Scenario: CouchDB failure or corruption
# Action: Stop peer, delete world state, restart peer, let Fabric replay ledger to rebuild CouchDB

set -e

echo "=== CouchDB Recovery ==="
echo "Step 1: Stopping peer..."
docker stop peer0.org1.example.com

echo "Step 2: Deleting CouchDB world state database..."
docker exec couchdb0 curl -X DELETE http://admin:adminpw@localhost:5984/auditchannel_ || true

echo "Step 3: Clearing peer ledger state (not blocks)..."
docker exec peer0.org1.example.com sh -c "rm -rf /var/hyperledger/production/ledgerData/stateLeveldb" 2>/dev/null || true

echo "Step 4: Restarting peer..."
docker start peer0.org1.example.com

echo "Step 5: Waiting for peer to sync and rebuild CouchDB..."
sleep 30

echo "Step 6: Verifying CouchDB..."
for i in $(seq 1 12); do
  COUNT=$(docker exec couchdb0 curl -s http://admin:adminpw@localhost:5984/auditchannel_ | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('doc_count',0))" 2>/dev/null || echo "waiting")
  echo "  Attempt $i: CouchDB doc_count=$COUNT"
  if [ "$COUNT" != "waiting" ] && [ "$COUNT" -gt 0 ]; then
    echo "CouchDB rebuilt successfully with $COUNT documents"
    break
  fi
  sleep 10
done

echo "Step 7: Rebuilding MongoDB from ledger..."
python3 scripts/recover_mongodb.py

echo "=== CouchDB Recovery Complete ==="
