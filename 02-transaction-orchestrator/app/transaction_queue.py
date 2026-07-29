from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

BASE_DIR = Path(__file__).resolve().parent.parent
QUEUE_DIR = BASE_DIR / "queue" / "ordered_proposals"
QUEUE_DIR.mkdir(parents=True, exist_ok=True)

LIFECYCLE_ORDER = ["ai_recommendation", "human_override", "bdss", "crss", "credit_approval", "iris"]
TX_ORDER = ["TX001", "TX002", "TX003", "TX004", "TX005", "TX006"]
SERVICE_TX_MAP = dict(zip(LIFECYCLE_ORDER, TX_ORDER))


class TransactionQueue:
    def __init__(self):
        self._lock = threading.Lock()

    def _app_dir(self, application_id: str) -> Path:
        p = QUEUE_DIR / application_id
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _next_seq(self, application_id: str) -> int:
        existing = list(self._app_dir(application_id).glob("*.json"))
        if not existing:
            return 1
        seqs = []
        for f in existing:
            try:
                seqs.append(int(f.stem.split("_")[0]))
            except (ValueError, IndexError):
                continue
        return max(seqs) + 1 if seqs else 1

    def enqueue(self, application_id: str, tx_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            seq = self._next_seq(application_id)
            tx_num = TX_ORDER.index(tx_type) + 1 if tx_type in TX_ORDER else 0
            entry = {
                "queue_id": str(uuid4()),
                "application_id": application_id,
                "tx_type": tx_type,
                "tx_num": tx_num,
                "sequence": seq,
                "service": LIFECYCLE_ORDER[tx_num - 1] if 1 <= tx_num <= len(LIFECYCLE_ORDER) else "unknown",
                "status": "queued",
                "enqueued_at": datetime.now(timezone.utc).isoformat(),
                "payload": payload,
            }
            fname = f"{seq:04d}_{tx_type}_{entry['queue_id'][:8]}.json"
            fpath = self._app_dir(application_id) / fname
            fpath.write_text(json.dumps(entry, indent=2), encoding="utf-8")
            return entry

    def dequeue(self, application_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            app_dir = self._app_dir(application_id)
            files = sorted(app_dir.glob("*.json"))
            for f in files:
                try:
                    entry = json.loads(f.read_text(encoding="utf-8"))
                    if entry.get("status") == "queued":
                        entry["status"] = "processing"
                        entry["dequeued_at"] = datetime.now(timezone.utc).isoformat()
                        f.write_text(json.dumps(entry, indent=2), encoding="utf-8")
                        return entry
                except (json.JSONDecodeError, KeyError):
                    continue
            return None

    def peek(self, application_id: str) -> Optional[Dict[str, Any]]:
        app_dir = self._app_dir(application_id)
        files = sorted(app_dir.glob("*.json"))
        for f in files:
            try:
                entry = json.loads(f.read_text(encoding="utf-8"))
                if entry.get("status") == "queued":
                    return entry
            except (json.JSONDecodeError, KeyError):
                continue
        return None

    def complete(self, application_id: str, queue_id: str) -> bool:
        with self._lock:
            app_dir = self._app_dir(application_id)
            for f in app_dir.glob("*.json"):
                try:
                    entry = json.loads(f.read_text(encoding="utf-8"))
                    if entry.get("queue_id") == queue_id:
                        entry["status"] = "completed"
                        entry["completed_at"] = datetime.now(timezone.utc).isoformat()
                        f.write_text(json.dumps(entry, indent=2), encoding="utf-8")
                        return True
                except (json.JSONDecodeError, KeyError):
                    continue
            return False

    def fail(self, application_id: str, queue_id: str, reason: str) -> bool:
        with self._lock:
            app_dir = self._app_dir(application_id)
            for f in app_dir.glob("*.json"):
                try:
                    entry = json.loads(f.read_text(encoding="utf-8"))
                    if entry.get("queue_id") == queue_id:
                        entry["status"] = "failed"
                        entry["failed_at"] = datetime.now(timezone.utc).isoformat()
                        entry["failure_reason"] = reason
                        f.write_text(json.dumps(entry, indent=2), encoding="utf-8")
                        return True
                except (json.JSONDecodeError, KeyError):
                    continue
            return False

    def get_queue(self, application_id: str) -> List[Dict[str, Any]]:
        app_dir = self._app_dir(application_id)
        results = []
        for f in sorted(app_dir.glob("*.json")):
            try:
                results.append(json.loads(f.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                continue
        return results

    def get_next_expected_tx(self, application_id: str) -> Optional[str]:
        queue = self.get_queue(application_id)
        completed_txs = {e["tx_type"] for e in queue if e["status"] == "completed"}
        for tx in TX_ORDER:
            if tx not in completed_txs:
                return tx
        return None

    def clear_application(self, application_id: str) -> int:
        with self._lock:
            app_dir = self._app_dir(application_id)
            count = len(list(app_dir.glob("*.json")))
            for f in app_dir.glob("*.json"):
                f.unlink()
            try:
                app_dir.rmdir()
            except OSError:
                pass
            return count

    def get_all_pending(self) -> List[Dict[str, Any]]:
        results = []
        for app_dir in QUEUE_DIR.iterdir():
            if app_dir.is_dir():
                for f in sorted(app_dir.glob("*.json")):
                    try:
                        entry = json.loads(f.read_text(encoding="utf-8"))
                        if entry.get("status") in ("queued", "processing"):
                            results.append(entry)
                    except json.JSONDecodeError:
                        continue
        return results
