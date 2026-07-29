"""
MongoDB Recovery Script

Scenario: MongoDB failure or data loss
Action: Re-export all committed blockchain transactions via the Fabric Adapter
  and rebuild the MongoDB read model from scratch.
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "07-block-indexer" / "app"))
from export_service import BlockchainExportService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("recover-mongodb")


def main():
    log.info("=== MongoDB Recovery ===")
    log.info("Step 1: Rebuilding MongoDB from Fabric Adapter...")

    svc = BlockchainExportService()
    svc.rebuild_all()

    total = svc.mongo.get_event_count()
    log.info("Step 2: Verification - %d events exported", total)

    states = list(svc.mongo.application_timelines.find({}, {"_id": 0}))
    log.info("Step 3: %d application timelines rebuilt", len(states))

    changes = svc.mongo.field_changes.count_documents({})
    log.info("Step 4: %d field changes rebuilt", changes)

    log.info("=== MongoDB Recovery Complete ===")
    log.info("Events: %d | Applications: %d | Field Changes: %d", total, len(states), changes)


if __name__ == "__main__":
    main()
