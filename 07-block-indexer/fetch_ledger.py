import sys, os, logging
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))
from fabric_client import FabricClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("fetch_ledger")

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ledger_output_data")

def format_event(event: dict) -> str:
    lines = []
    for k, v in event.items():
        if k == "metadata" and isinstance(v, dict):
            lines.append(f"{k}:")
            for mk, mv in v.items():
                lines.append(f"  {mk}: {mv}")
        else:
            lines.append(f"{k}: {v}")
    return "\n".join(lines)

def _event_key_exists(event_key: str) -> bool:
    prefix = f"{event_key}_"
    for fname in os.listdir(OUT_DIR):
        if fname.startswith(prefix) and fname.endswith(".txt"):
            return True
    return False

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    client = FabricClient()
    events = client.get_all_events()
    log.info("Fetched %d events from Fabric Adapter", len(events))

    for event in events:
        event_key = event.get("eventKey", "")
        if not event_key:
            continue
        if _event_key_exists(event_key):
            log.info("Already extracted (skipping): %s", event_key)
            continue
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        filename = f"{event_key}_{ts}.txt"
        filepath = os.path.join(OUT_DIR, filename)
        content = format_event(event)
        with open(filepath, "w") as f:
            f.write(content)
        log.info("Written: %s", filename)

    total = len(os.listdir(OUT_DIR))
    log.info("Done. %d file(s) in ledger_output_data", total)

if __name__ == "__main__":
    main()
