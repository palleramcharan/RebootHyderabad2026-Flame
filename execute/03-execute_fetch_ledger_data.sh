#!/usr/bin/env bash
# execute_fetch_ledger_data.sh — Index Fabric events into MongoDB, then query
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"

echo "============================================"
echo "  Step 1: Verify MongoDB is running"
echo "============================================"
if ! docker ps --filter "name=mongodb" --format "{{.Names}}" 2>/dev/null | grep -q mongodb; then
  echo "ERROR: MongoDB not running. Start it with:"
  echo "  docker run -d --name mongodb -p 27017:27017 mongo:7"
  exit 1
fi
echo "MongoDB is running."

echo ""
echo "============================================"
echo "  Step 2: Verify Fabric Adapter is reachable"
echo "============================================"
if ! curl -sf http://localhost:8080/health/live > /dev/null 2>&1; then
  echo "ERROR: Fabric Adapter not reachable on http://localhost:8080"
  exit 1
fi
echo "Fabric Adapter is ready."

echo ""
echo "============================================"
echo "  Step 3: Index events from Fabric into MongoDB"
echo "============================================"
export FABRIC_ADAPTER_URL=http://localhost:8080
py 07-block-indexer/app/__main__.py --once

echo ""
echo "============================================"
echo "  Step 4: Query indexed data from MongoDB"
echo "============================================"
echo ""
echo "--- Total indexed events ---"
docker exec mongodb mongosh blockchain_index --quiet \
  --eval "db.audit_events.countDocuments()"

echo ""
echo "--- Events by service ---"
docker exec mongodb mongosh blockchain_index --quiet \
  --eval "db.audit_events.aggregate([{\$group:{_id:'\$service',count:{\$sum:1}}}]).forEach(d => print(d._id + ': ' + d.count))"

echo ""
echo "--- All event keys ---"
docker exec mongodb mongosh blockchain_index --quiet \
  --eval "db.audit_events.find().sort({timestamp:1}).forEach(d => print(d.eventKey + ' | ' + d.service + ' | ' + d.eventType))"

echo ""
echo "============================================"
echo "  Step 5: Comparison — Fabric Adapter vs MongoDB"
echo "============================================"
FABRIC_COUNT=$(curl -s http://localhost:8080/audit/events | python -c "import sys,json; print(len(json.load(sys.stdin)))")
MONGO_COUNT=$(docker exec mongodb mongosh blockchain_index --quiet --eval "db.audit_events.countDocuments()" 2>/dev/null | tail -1)

echo "Fabric Adapter events: $FABRIC_COUNT"
echo "MongoDB indexed events: $MONGO_COUNT"

if [ "$FABRIC_COUNT" = "$MONGO_COUNT" ]; then
  echo "MATCH: All Fabric events are indexed in MongoDB."
else
  echo "MISMATCH: Some events may not be indexed yet."
fi

echo ""
echo "=== Fetch complete ==="
