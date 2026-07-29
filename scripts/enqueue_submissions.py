"""Read submissions from 01-business-services and enqueue them into the transaction queue."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "02-transaction-orchestrator" / "app"))
from transaction_queue import TransactionQueue, SERVICE_TX_MAP

BASE = Path(__file__).resolve().parent.parent / "01-business-services"
queue = TransactionQueue()

SERVICE_DIR_MAP = {
    "01-ai-recommendation-engine": "ai_recommendation",
    "02-human-override": "human_override",
    "03-bdss": "bdss",
    "04-crss": "crss",
    "05-credit-approval": "credit_approval",
    "06-iris": "iris",
}

count = 0
for dir_name, service in SERVICE_DIR_MAP.items():
    sub_dir = BASE / dir_name / "submissions"
    if not sub_dir.exists():
        continue
    for f in sorted(sub_dir.glob("*.json")):
        data = json.loads(f.read_text("utf-8"))
        app_id = data.get("application_id", "UNKNOWN")
        tx_type = SERVICE_TX_MAP.get(service)
        payload = data.get("data", {})
        entry = queue.enqueue(app_id, tx_type, payload)
        print(f"Enqueued {entry['application_id']} / {entry['tx_type']} (queue_id={entry['queue_id']})")
        count += 1

print(f"\nTotal: {count} items enqueued")
