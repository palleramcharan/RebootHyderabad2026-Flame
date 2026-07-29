from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from transaction_queue import TransactionQueue
from lifecycle_manager import LifecycleManager
from orchestrator import Orchestrator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S%z",
)
logger = logging.getLogger("worker")

ADAPTER_ENABLED = os.environ.get("ADAPTER_ENABLED", "true").lower() == "true"
ADAPTER_URL = os.environ.get("ADAPTER_URL", "http://localhost:8080")
POLL_INTERVAL_ACTIVE_SEC = int(os.environ.get("POLL_INTERVAL_ACTIVE_SEC", "5"))
POLL_INTERVAL_IDLE_SEC = int(os.environ.get("POLL_INTERVAL_IDLE_SEC", "60"))


def create_orchestrator() -> Orchestrator:
    queue = TransactionQueue()
    lifecycle = LifecycleManager()
    adapter = None
    if ADAPTER_ENABLED:
        try:
            from nodejs_adapter import NodeJsAdapter
            adapter = NodeJsAdapter(ADAPTER_URL)
            if adapter.is_adapter_ready():
                logger.info("Fabric adapter ready at %s", ADAPTER_URL)
            else:
                logger.warning("Fabric adapter at %s not reachable, running in queue-only mode", ADAPTER_URL)
        except Exception as e:
            logger.warning("Fabric adapter init failed: %s", e)
    else:
        logger.info("Fabric adapter disabled (ADAPTER_ENABLED=false), queue-only mode")
    return Orchestrator(queue, lifecycle, adapter)


def has_pending_work() -> bool:
    qdir = Path(__file__).resolve().parent.parent / "queue" / "ordered_proposals"
    if not qdir.exists():
        return False
    for app_dir in qdir.iterdir():
        if app_dir.is_dir():
            for f in app_dir.glob("*.json"):
                try:
                    data = json.loads(f.read_text("utf-8"))
                    if data.get("status") in ("queued", "processing"):
                        return True
                except Exception:
                    continue
    return False


def process_batch_job():
    logger.info("=== Batch window trigger at %s ===", datetime.now(timezone.utc).isoformat())
    orchestrator = create_orchestrator()
    try:
        result = orchestrator.process_batch()
        logger.info("Batch result: processed=%d, status=%s", result["processed"], result["status"])
        if result["results"]:
            for r in result["results"]:
                logger.info("  %s | %s | %s", r.get("application_id"), r.get("tx_type"), r.get("status"))
    except Exception as e:
        logger.error("Batch processing failed: %s", e, exc_info=True)


def run_loop():
    logger.info("Worker loop starting (adapter=%s)", ADAPTER_ENABLED)
    while True:
        process_batch_job()
        interval = POLL_INTERVAL_ACTIVE_SEC if has_pending_work() else POLL_INTERVAL_IDLE_SEC
        logger.debug("Polling again in %ds", interval)
        time.sleep(interval)


def run_once():
    logger.info("Running single batch (one-shot)")
    process_batch_job()


if __name__ == "__main__":
    if "--once" in sys.argv:
        run_once()
    else:
        try:
            run_loop()
        except KeyboardInterrupt:
            logger.info("Worker stopped by signal")
