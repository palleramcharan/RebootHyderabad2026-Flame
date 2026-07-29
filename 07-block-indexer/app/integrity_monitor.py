import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from mongo_client import MongoStore

logger = logging.getLogger("integrity_monitor")

FABRIC_ADAPTER_URL = "http://localhost:8080"


class IntegrityMonitor:
    def __init__(self, adapter_url: str = FABRIC_ADAPTER_URL, mongo: Optional[MongoStore] = None):
        self.adapter_url = adapter_url.rstrip("/")
        self.mongo = mongo or MongoStore()

    def _fetch_application_events(self, application_id: str) -> List[Dict[str, Any]]:
        resp = httpx.get(f"{self.adapter_url}/audit/applications/{application_id}/events", timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _fetch_statistics(self) -> Dict[str, Any]:
        resp = httpx.get(f"{self.adapter_url}/audit/statistics", timeout=15)
        resp.raise_for_status()
        return resp.json()

    def verify_application_hash_chain(self, application_id: str) -> Dict[str, Any]:
        events = self._fetch_application_events(application_id)
        events.sort(key=lambda e: e.get("sequence", 0))

        entries = []
        chain_intact = True

        for i, evt in enumerate(events):
            expected_prev_hash = events[i - 1].get("currentHash", "") if i > 0 else ""
            prev_match = evt.get("previousHash", "") == expected_prev_hash

            hash_input = "|".join([
                evt.get("applicationId", ""),
                evt.get("businessEvent", ""),
                evt.get("timestamp", ""),
                evt.get("evidenceHash", ""),
                evt.get("previousHash", ""),
                evt.get("correlationId", ""),
                json.dumps(evt.get("changedFields", []), sort_keys=True, separators=(',', ':')),
                str(evt.get("sequence", 0)),
            ])
            computed_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()
            hash_match = computed_hash == evt.get("currentHash", "")

            if not prev_match or not hash_match:
                chain_intact = False

            entries.append({
                "sequence": evt.get("sequence"),
                "auditId": evt.get("auditId"),
                "eventKey": evt.get("eventKey"),
                "previousHashMatch": prev_match,
                "currentHashMatch": hash_match,
            })

        return {
            "applicationId": application_id,
            "chainIntact": chain_intact,
            "eventCount": len(events),
            "entries": entries,
        }

    def verify_evidence_hash(self, event_key: str, evidence_hash: str) -> Dict[str, Any]:
        try:
            resp = httpx.post(
                f"{self.adapter_url}/audit/verify-evidence/{event_key}",
                json={"evidenceHash": evidence_hash},
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"eventKey": event_key, "verified": False, "error": str(e)}

    def verify_all_applications(self) -> Dict[str, Any]:
        stats = self._fetch_statistics()
        app_ids = list(stats.get("byApplication", {}).keys())

        results = []
        all_intact = True
        for app_id in app_ids:
            result = self.verify_application_hash_chain(app_id)
            results.append(result)
            if not result["chainIntact"]:
                all_intact = False

        check_record = {
            "applicationId": "ALL",
            "allIntact": all_intact,
            "applicationsChecked": len(app_ids),
            "totalEvents": stats.get("totalEvents", 0),
            "results": results,
            "checkedAt": datetime.now(timezone.utc).isoformat(),
        }
        self.mongo.upsert_integrity_check("ALL", check_record)
        return check_record

    def check_consistency(self) -> Dict[str, Any]:
        mongo_count = self.mongo.audit_events.count_documents({})

        try:
            stats = self._fetch_statistics()
            fabric_count = stats.get("totalEvents", 0)
        except Exception:
            fabric_count = -1

        match = mongo_count == fabric_count if fabric_count >= 0 else False

        return {
            "mongoEventCount": mongo_count,
            "fabricEventCount": fabric_count,
            "countsMatch": match,
            "checkedAt": datetime.now(timezone.utc).isoformat(),
        }
