from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from transaction_queue import SERVICE_TX_MAP, TX_ORDER, TransactionQueue
from lifecycle_manager import LifecycleManager, LIFECYCLE, TX_TO_SERVICE
from fabric_connector import FabricConnector
from evidence_client import EvidenceClient
from field_change_detector import detect_changes

logger = logging.getLogger("orchestrator")


class Orchestrator:
    def __init__(
        self,
        queue: TransactionQueue,
        lifecycle: LifecycleManager,
        adapter: Optional[FabricConnector] = None,
        evidence: Optional[EvidenceClient] = None,
    ):
        self.queue = queue
        self.lifecycle = lifecycle
        self.adapter = adapter
        self.evidence = evidence or EvidenceClient()

    def _resolve_previous_hash(self, application_id: str, current_sequence: int = 0) -> str:
        if not self.adapter:
            return ""
        try:
            events = self.adapter.get_application_audit_history(application_id)
            if events and len(events) > 0:
                prev_events = [e for e in events if e.get("sequence", 0) < current_sequence]
                if prev_events:
                    return prev_events[-1].get("currentHash", "")
        except Exception as e:
            logger.warning("Failed to resolve previous hash for %s: %s", application_id, e)
        return ""

    def _resolve_previous_payload(self, application_id: str) -> Optional[Dict[str, Any]]:
        state = self.lifecycle.get_current_state(application_id)
        if state and state.get("history"):
            last_step = state["history"][-1]["step"] if state["history"] else None
            if last_step:
                try:
                    state_path = self.lifecycle._state_path(application_id)
                    if state_path.exists():
                        data = json.loads(state_path.read_text("utf-8"))
                        return data.get("lastPayload", {})
                except Exception:
                    pass
        return None

    def process_batch(self) -> Dict[str, Any]:
        pending = self.queue.get_all_pending()
        if not pending:
            return {"status": "idle", "processed": 0, "results": []}

        results = []
        by_app: Dict[str, List[Dict]] = {}
        for entry in pending:
            aid = entry["application_id"]
            by_app.setdefault(aid, []).append(entry)

        for app_id, entries in by_app.items():
            ordered = self._order_transactions(app_id, entries)
            for entry in ordered:
                result = self._process_one(app_id, entry)
                results.append(result)

        return {"status": "complete", "processed": len(results), "results": results}

    def _order_transactions(self, app_id: str, entries: List[Dict]) -> List[Dict]:
        ordered = sorted(entries, key=lambda e: TX_ORDER.index(e["tx_type"]) if e["tx_type"] in TX_ORDER else 999)
        current_step = self.lifecycle.get_current_step(app_id)
        if not current_step:
            expected_tx = "TX001"
        else:
            expected_tx = self.lifecycle.get_next_tx(app_id)
        if not expected_tx:
            return []
        filtered = [e for e in ordered if e["tx_type"] == expected_tx]
        if not filtered:
            return []
        return filtered[:1]

    def _process_one(self, app_id: str, entry: Dict) -> Dict:
        tx_type = entry["tx_type"]
        queue_id = entry["queue_id"]
        service = entry.get("service", TX_TO_SERVICE.get(tx_type, "unknown"))
        payload = entry.get("payload", {})

        logger.info("Processing %s for %s (queue_id=%s)", tx_type, app_id, queue_id)

        validation = self.lifecycle.validate_transition(app_id, service)
        if not validation["valid"]:
            self.queue.fail(app_id, queue_id, validation["message"])
            return {"application_id": app_id, "queue_id": queue_id, "tx_type": tx_type, "status": "failed", "reason": validation["message"]}

        dequeued = self.queue.dequeue(app_id)
        if not dequeued:
            return {"application_id": app_id, "queue_id": queue_id, "tx_type": tx_type, "status": "skipped", "reason": "dequeue returned None"}

        ledger_ok = False
        ledger_result = ""
        if self.adapter:
            try:
                correlation_id = entry.get("correlation_id", str(uuid4()))
                ledger_result = self._submit_audit_event(app_id, tx_type, service, payload, correlation_id)
                ledger_ok = True
            except Exception as e:
                ledger_result = str(e)
                logger.error("Ledger submission failed cid=%s for %s/%s: %s", correlation_id, app_id, tx_type, e)

        if ledger_ok:
            self.lifecycle.advance(app_id, service)
            self.queue.complete(app_id, queue_id)
            status = "completed"
        else:
            self.queue.fail(app_id, queue_id, ledger_result)
            status = "failed"

        return {
            "application_id": app_id,
            "queue_id": queue_id,
            "tx_type": tx_type,
            "service": service,
            "status": status,
            "ledger_result": ledger_result,
        }

    def _submit_audit_event(self, app_id: str, tx_type: str, service: str, payload: Dict, correlation_id: str) -> Dict:
        step_info = LIFECYCLE.get(service, {})
        sequence = int(tx_type.replace("TX", ""))
        previous_hash = self._resolve_previous_hash(app_id, sequence)
        previous_payload = self._resolve_previous_payload(app_id)
        changed_fields = detect_changes(previous_payload, payload)

        evidence_result = self.evidence.store_evidence(
            submission_id=f"{app_id}-{tx_type}",
            application_id=app_id,
            service=service,
            business_event=f"TX_{tx_type}",
            payload=payload,
        )
        evidence_hash = evidence_result.get("evidenceHash", "")

        audit_id = str(uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        hash_input = "|".join([
            app_id, f"TX_{tx_type}", timestamp, evidence_hash,
            previous_hash, correlation_id, json.dumps(changed_fields, separators=(',', ':')), str(sequence),
        ])
        current_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

        audit_event = {
            "auditId": audit_id,
            "applicationId": app_id,
            "submissionId": f"{app_id}-{tx_type}",
            "correlationId": correlation_id,
            "businessEvent": f"TX_{tx_type}",
            "workflowStep": service,
            "service": service,
            "operation": "UPDATE",
            "userId": "SYSTEM",
            "timestamp": timestamp,
            "eventCategory": "AUDIT",
            "eventSeverity": "INFO",
            "sequence": sequence,
            "eventVersion": "2.0",
            "currentHash": current_hash,
            "previousHash": previous_hash,
            "evidenceHash": evidence_hash,
            "transactionId": "",
            "blockNumber": 0,
            "channelName": "auditchannel",
            "mspId": "Org1MSP",
            "eventKey": "",
            "changedFields": changed_fields,
            "metadata": {"payload": payload},
        }

        return self.adapter.submit_audit_event(audit_event)
