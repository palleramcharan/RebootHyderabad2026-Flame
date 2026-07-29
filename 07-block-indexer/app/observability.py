import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from mongo_client import MongoStore

logger = logging.getLogger("observability")

FABRIC_ADAPTER_URL = "http://localhost:8080"
EVIDENCE_VAULT_URL = "http://localhost:8001"


class ObservabilityService:
    def __init__(self, mongo: Optional[MongoStore] = None):
        self.mongo = mongo or MongoStore()

    def collect_metrics(self) -> Dict[str, Any]:
        mongo_count = self.mongo.audit_events.count_documents({})
        app_count = self.mongo.application_timelines.count_documents({})
        field_change_count = self.mongo.field_changes.count_documents({})

        metrics = {
            "totalEvents": mongo_count,
            "totalApplications": app_count,
            "totalFieldChanges": field_change_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        for key, value in metrics.items():
            if key != "timestamp":
                self.mongo.upsert_metric(key, value)

        return metrics

    def check_peer_health(self) -> Dict[str, Any]:
        try:
            resp = httpx.get(f"{FABRIC_ADAPTER_URL}/health", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "service": "fabric-adapter",
                    "status": "UP",
                    "channel": data.get("channel", "unknown"),
                    "chaincode": data.get("chaincode", "unknown"),
                    "peer": data.get("peer", "unknown"),
                }
            return {"service": "fabric-adapter", "status": "DEGRADED", "httpStatus": resp.status_code}
        except Exception as e:
            return {"service": "fabric-adapter", "status": "DOWN", "error": str(e)}

    def check_evidence_vault_health(self) -> Dict[str, Any]:
        try:
            resp = httpx.get(f"{EVIDENCE_VAULT_URL}/health", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "service": "evidence-vault",
                    "status": "UP",
                    "evidenceCount": data.get("evidenceCount", 0),
                }
            return {"service": "evidence-vault", "status": "DEGRADED", "httpStatus": resp.status_code}
        except Exception as e:
            return {"service": "evidence-vault", "status": "DOWN", "error": str(e)}

    def check_mongodb_health(self) -> Dict[str, Any]:
        try:
            count = self.mongo.audit_events.count_documents({})
            return {"service": "mongodb", "status": "UP", "eventCount": count}
        except Exception as e:
            return {"service": "mongodb", "status": "DOWN", "error": str(e)}

    def get_all_health(self) -> Dict[str, Any]:
        return {
            "status": "UP" if all(h["status"] == "UP" for h in [
                self.check_peer_health(),
                self.check_evidence_vault_health(),
                self.check_mongodb_health(),
            ]) else "DEGRADED",
            "services": {
                "fabricAdapter": self.check_peer_health(),
                "evidenceVault": self.check_evidence_vault_health(),
                "mongodb": self.check_mongodb_health(),
            },
            "metrics": self.collect_metrics(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
