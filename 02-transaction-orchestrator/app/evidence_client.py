import json
import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger("evidence_client")

EVIDENCE_VAULT_URL = "http://localhost:8001"


class EvidenceClient:
    def __init__(self, base_url: str = EVIDENCE_VAULT_URL):
        self.base_url = base_url.rstrip("/")

    def store_evidence(self, submission_id: str, application_id: str, service: str,
                       business_event: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            resp = httpx.post(f"{self.base_url}/evidence", json={
                "submissionId": submission_id,
                "applicationId": application_id,
                "service": service,
                "businessEvent": business_event,
                "payload": payload,
            }, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning("Evidence vault unavailable, computing local hash: %s", e)
            import hashlib
            local_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
            return {"evidenceHash": local_hash}

    def get_evidence(self, submission_id: str, version: Optional[int] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/evidence/{submission_id}"
        if version:
            url += f"?version={version}"
        resp = httpx.get(url, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def verify_evidence(self, submission_id: str, evidence_hash: str) -> Dict[str, Any]:
        resp = httpx.post(f"{self.base_url}/evidence/{submission_id}/verify",
                          json={"evidenceHash": evidence_hash}, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def is_ready(self) -> bool:
        try:
            resp = httpx.get(f"{self.base_url}/health", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False
