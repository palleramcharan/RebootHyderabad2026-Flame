#!/usr/bin/env bash
# execute_fabric.sh — Start infrastructure, run worker, verify events
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"

echo "============================================"
echo "  Step 1: Start MongoDB (if not running)"
echo "============================================"
if docker ps --filter "name=mongodb" --format "{{.Names}}" 2>/dev/null | grep -q mongodb; then
  echo "MongoDB already running."
else
  echo "Starting MongoDB container..."
  docker run -d --name mongodb -p 27017:27017 mongo:7
fi

echo ""
echo "============================================"
echo "  Step 2: Verify Fabric network is up"
echo "============================================"
if ! docker ps --filter "name=peer0.org1.example.com" --format "{{.Names}}" 2>/dev/null | grep -q peer0; then
  echo "ERROR: Fabric network not running. Start it with:"
  echo "  cd 05-fabric-network && docker compose up -d"
  echo "Then create channel and deploy chaincode:"
  echo "  cd 05-fabric-network && ./scripts/create-channel.sh"
  echo "  cd 05-fabric-network && ./scripts/deploy-chaincode.sh audit-contract ..."
  exit 1
fi
echo "Fabric network is running."

if ! curl -sf http://localhost:8080/health/live > /dev/null 2>&1; then
  echo "ERROR: Fabric Adapter not reachable on http://localhost:8080"
  exit 1
fi
echo "Fabric Adapter is ready."

echo ""
echo "============================================"
echo "  Step 3: Copy chaincode to CLI container"
echo "============================================"
docker exec cli mkdir -p /opt/gopath/src/github.com/hyperledger/fabric/peer/chaincode/audit-contract/lib/models 2>/dev/null
docker cp 06-chaincode/audit-contract/. cli:/opt/gopath/src/github.com/hyperledger/fabric/peer/chaincode/audit-contract/
echo "Chaincode copied."

echo ""
echo "============================================"
echo "  Step 4: Seed transaction queue from existing submissions"
echo "============================================"
py scripts/enqueue_submissions.py

echo ""
echo "============================================"
echo "  Step 5: Process queue items"
echo "============================================"
export ADAPTER_URL=http://localhost:8080

MAX_ATTEMPTS=10
ATTEMPT=1
TOTAL_PROCESSED=0

while [ $ATTEMPT -le $MAX_ATTEMPTS ]; do
  echo ""
  echo "--- Batch attempt $ATTEMPT ---"
  OUTPUT=$(py 02-transaction-orchestrator/app/worker.py --once 2>&1)
  echo "$OUTPUT"

  PROCESSED=$(echo "$OUTPUT" | grep -o 'processed=[0-9]*' | grep -o '[0-9]*')
  if [ -z "$PROCESSED" ] || [ "$PROCESSED" -eq 0 ]; then
    echo "No more items to process. Done."
    break
  fi

  TOTAL_PROCESSED=$((TOTAL_PROCESSED + PROCESSED))
  ATTEMPT=$((ATTEMPT + 1))
  sleep 1
done

echo ""
echo "Total processed across all batches: $TOTAL_PROCESSED"

echo ""
echo "============================================"
echo "  Step 6: Verify events on Fabric Adapter"
echo "============================================"
curl -s http://localhost:8080/audit/events | python -c "
import sys, json
events = json.load(sys.stdin)
print(f'{len(events)} audit event(s) on Fabric ledger:')
for e in events:
    print(f'  {e[\"eventKey\"]}  |  {e[\"service\"]}  |  {e[\"eventType\"]}')
"

echo ""
echo "=== Fabric execution complete ==="
