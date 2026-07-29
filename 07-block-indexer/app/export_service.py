import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional

import httpx

from mongo_client import MongoStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("blockchain-export-service")

FABRIC_ADAPTER_URL = os.getenv("FABRIC_ADAPTER_URL", "http://localhost:8080")
POLL_BUSY_SEC = int(os.getenv("POLL_BUSY_SEC", "15"))
POLL_IDLE_SEC = int(os.getenv("POLL_IDLE_SEC", "60"))


class BlockchainExportService:
    def __init__(self, adapter_url: Optional[str] = None, mongo: Optional[MongoStore] = None):
        self.adapter_url = (adapter_url or FABRIC_ADAPTER_URL).rstrip("/")
        self.mongo = mongo or MongoStore()

    def fetch_events(self) -> list:
        resp = httpx.get(f"{self.adapter_url}/audit/events", timeout=30)
        resp.raise_for_status()
        return resp.json()

    def fetch_application_events(self, application_id: str) -> list:
        resp = httpx.get(f"{self.adapter_url}/audit/applications/{application_id}/events", timeout=30)
        resp.raise_for_status()
        return resp.json()

    def fetch_statistics(self) -> dict:
        resp = httpx.get(f"{self.adapter_url}/audit/statistics", timeout=15)
        resp.raise_for_status()
        return resp.json()

    def sync_once(self) -> int:
        log.info("Starting export sync cycle...")
        try:
            events = self.fetch_events()
        except Exception as e:
            log.error("Failed to fetch events from Fabric Adapter: %s", e)
            return 0

        existing_keys = self.mongo.get_indexed_event_keys()
        new_count = 0

        for event in events:
            event_key = event.get("eventKey", "")
            if not event_key:
                continue
            if event_key in existing_keys:
                continue
            if self.mongo.upsert_audit_event(event):
                log.info("Exported new event: %s", event_key)
                new_count += 1

        if new_count > 0:
            try:
                stats = self.fetch_statistics()
                self.mongo.upsert_metric("totalEvents", stats.get("totalEvents", 0))
                self.mongo.upsert_metric("eventsByService", stats.get("byService", {}))
                self.mongo.upsert_metric("eventsBySeverity", stats.get("bySeverity", {}))
                self.mongo.upsert_metric("eventsByApplication", stats.get("byApplication", {}))
                self.mongo.upsert_metric("applicationsTracked", len(stats.get("byApplication", {})))
                self.mongo.upsert_metric("servicesTracked", len(stats.get("byService", {})))

                self.mongo.rebuild_application_timelines()
                self.mongo.rebuild_field_changes()
            except Exception as e:
                log.error("Failed to update derived collections: %s", e)

        total = self.mongo.get_event_count()
        log.info("Export cycle complete: %d new, %d total exported", new_count, total)
        return new_count

    def rebuild_all(self):
        log.info("=== FULL REBUILD ===")
        self.mongo.audit_events.delete_many({})
        self.mongo.application_timelines.delete_many({})
        self.mongo.field_changes.delete_many({})
        self.mongo.block_metadata.delete_many({})
        self.mongo.integrity_checks.delete_many({})
        self.mongo.blockchain_metrics.delete_many({})
        log.info("Cleared all MongoDB collections")

        try:
            events = self.fetch_events()
        except Exception as e:
            log.error("Failed to fetch events: %s", e)
            return

        for event in events:
            self.mongo.upsert_audit_event(event)

        self.mongo.rebuild_application_timelines()
        self.mongo.rebuild_field_changes()
        log.info("Rebuild complete: %d events exported", len(events))

    def run_forever(self):
        log.info("Blockchain Export Service started. Polling Fabric Adapter at %s", self.adapter_url)
        while True:
            try:
                new = self.sync_once()
                interval = POLL_BUSY_SEC if new > 0 else POLL_IDLE_SEC
            except Exception as e:
                log.error("Unexpected error: %s", e)
                interval = POLL_IDLE_SEC
            time.sleep(interval)


if __name__ == "__main__":
    import sys
    svc = BlockchainExportService()
    if "--rebuild" in sys.argv:
        svc.rebuild_all()
    elif "--once" in sys.argv:
        svc.sync_once()
    else:
        svc.run_forever()
