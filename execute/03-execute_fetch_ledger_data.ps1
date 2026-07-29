Write-Host "============================================"
Write-Host "  Step 1: Verify MongoDB is running"
Write-Host "============================================"
$mongo = docker ps --filter "name=mongodb" --format "{{.Names}}" 2>$null
if ($mongo -notmatch "mongodb") {
  Write-Host "ERROR: MongoDB not running. Start it with:"
  Write-Host "  docker run -d --name mongodb -p 27017:27017 mongo:7"
  exit 1
}
Write-Host "MongoDB is running."

Write-Host ""
Write-Host "============================================"
Write-Host "  Step 2: Verify Fabric Adapter is reachable"
Write-Host "============================================"
try {
  $null = Invoke-WebRequest -Uri http://localhost:8080/health/live -UseBasicParsing -ErrorAction Stop
  Write-Host "Fabric Adapter is ready."
} catch {
  Write-Host "ERROR: Fabric Adapter not reachable on http://localhost:8080"
  exit 1
}

Write-Host ""
Write-Host "============================================"
Write-Host "  Step 3: Index events from Fabric into MongoDB"
Write-Host "============================================"
$env:FABRIC_ADAPTER_URL = "http://localhost:8080"
.\.venv\Scripts\python 07-block-indexer/app/__main__.py --once

Write-Host ""
Write-Host "============================================"
Write-Host "  Step 4: Query indexed data from MongoDB"
Write-Host "============================================"
Write-Host ""
Write-Host "--- Total indexed events ---"
docker exec mongodb mongosh audit_ledger --quiet --eval 'db.audit_events.countDocuments()'

Write-Host ""
Write-Host "--- Events by service ---"
docker exec mongodb mongosh audit_ledger --quiet --eval 'db.audit_events.aggregate([{$group:{_id:`$service`,count:{$sum:1}}}]).forEach(d => print(d._id + `: ` + d.count))'

Write-Host ""
Write-Host "--- All event keys ---"
docker exec mongodb mongosh audit_ledger --quiet --eval 'db.audit_events.find().sort({timestamp:1}).forEach(d => print(d.eventKey + ` | ` + d.service + ` | ` + d.eventType))'

Write-Host ""
Write-Host "============================================"
Write-Host "  Step 5: Export events to ledger_output_data"
Write-Host "============================================"
$outDir = Resolve-Path "$PSScriptRoot\..\07-block-indexer\ledger_output_data"
.\.venv\Scripts\python -c @"
import json, os, sys
from pymongo import MongoClient

db = MongoClient('mongodb://localhost:27017').audit_ledger
outdir = r'$($outDir)'
os.makedirs(outdir, exist_ok=True)

events = list(db.audit_events.find({}, {'_id': 0}).sort('timestamp', 1))
for ev in events:
    key = ev.get('eventKey', 'unknown')
    fpath = os.path.join(outdir, f'{key}.txt')
    with open(fpath, 'w', encoding='utf-8') as f:
        for k, v in ev.items():
            if isinstance(v, dict):
                f.write(f'{k}:\n')
                for sk, sv in v.items():
                    f.write(f'  {sk}: {json.dumps(sv) if isinstance(sv, str) else sv}\n')
            elif isinstance(v, list):
                f.write(f'{k}: {json.dumps(v)}\n')
            else:
                f.write(f'{k}: {v}\n')
print(f'Exported {len(events)} event(s) to {outdir}')
"@

Write-Host ""
Write-Host "============================================"
Write-Host "  Step 6: Comparison - Fabric Adapter vs MongoDB"
Write-Host "============================================"
$fabricCount = (Invoke-RestMethod -Uri http://localhost:8080/audit/events -UseBasicParsing).Count
$mongoCount = docker exec mongodb mongosh audit_ledger --quiet --eval 'db.audit_events.countDocuments()' 2>$null | Select-Object -Last 1

Write-Host "Fabric Adapter events: $fabricCount"
Write-Host "MongoDB indexed events: $mongoCount"

if ($fabricCount -eq $mongoCount) {
  Write-Host "MATCH: All Fabric events are indexed in MongoDB."
} else {
  Write-Host "MISMATCH: Some events may not be indexed yet."
}

Write-Host ""
Write-Host "=== Fetch complete ==="
