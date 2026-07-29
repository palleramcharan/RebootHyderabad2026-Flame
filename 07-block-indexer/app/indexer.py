import logging
import time
import os

from fabric_client import FabricClient
from mongo_client import MongoStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("block-indexer")

POLL_INTERVAL_BUSY = int(os.getenv("POLL_INTERVAL_BUSY", "15"))
POLL_INTERVAL_IDLE = int(os.getenv("POLL_INTERVAL_IDLE", "60"))


class BlockIndexer:
    def __init__(self, fabric: FabricClient | None = None, mongo: MongoStore | None = None):
        self.fabric = fabric or FabricClient()
        self.mongo = mongo or MongoStore()
        self._indexed_count = 0

    def sync_once(self) -> int:
        log.info("Starting sync cycle...")
        try:
            events = self.fabric.get_all_events()
        except Exception as e:
            log.error("Failed to fetch events from Fabric Adapter: %s", e)
            return 0

        existing_keys = self.mongo.get_indexed_keys()
        new_count = 0

        for event in events:
            event_key = event.get("eventKey", "")
            if not event_key:
                continue
            if event_key in existing_keys:
                continue
            if self.mongo.upsert_event(event):
                log.info("Indexed new event: %s", event_key)
                new_count += 1

        self._indexed_count += new_count
        total = self.mongo.get_event_count()
        log.info("Sync complete: %d new, %d total indexed", new_count, total)
        return new_count

    def run_forever(self):
        log.info("Block Indexer started. Polling Fabric Adapter...")
        while True:
            try:
                new = self.sync_once()
                interval = POLL_INTERVAL_BUSY if new > 0 else POLL_INTERVAL_IDLE
            except Exception as e:
                log.error("Unexpected error: %s", e)
                interval = POLL_INTERVAL_IDLE
            log.debug("Next poll in %ds...", interval)
            time.sleep(interval)
