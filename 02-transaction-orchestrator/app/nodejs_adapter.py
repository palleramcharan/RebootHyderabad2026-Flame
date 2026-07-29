from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import httpx

from fabric_connector import FabricConnector

logger = logging.getLogger("nodejs_adapter")

DEFAULT_URL = "http://localhost:8080"
MAX_RETRIES = 3
BASE_DELAY_SEC = 1.0


class NodeJsAdapter(FabricConnector):
    def __init__(self, adapter_url: str = DEFAULT_URL):
        self.adapter_url = adapter_url

    def submit_audit_event(self, audit_event: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.adapter_url}/audit/events"
        last_error = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = httpx.post(url, json=audit_event, timeout=30)
                resp.raise_for_status()
                result = resp.json()
                logger.info("Audit committed auditId=%s eventKey=%s", audit_event.get("auditId"), result.get("eventKey"))
                return result
            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    delay = BASE_DELAY_SEC * (2 ** (attempt - 1))
                    logger.warning("Retry %d/%d for auditId=%s in %.1fs: %s", attempt, MAX_RETRIES, audit_event.get("auditId"), delay, e)
                    time.sleep(delay)
        raise RuntimeError(f"Audit event submission failed after {MAX_RETRIES} retries: {last_error}")

    def get_application_audit_history(self, application_id: str) -> List[Dict[str, Any]]:
        url = f"{self.adapter_url}/audit/applications/{application_id}/events"
        resp = httpx.get(url, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def verify_on_ledger(self, event_key: str, expected_hash: Optional[str] = None) -> Dict[str, Any]:
        base = f"{self.adapter_url}/audit/events/{event_key}"
        params = {}
        if expected_hash:
            params = {"expectedHash": expected_hash}
        resp = httpx.get(base, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def is_adapter_ready(self) -> bool:
        try:
            url = f"{self.adapter_url}/health"
            resp = httpx.get(url, timeout=10)
            return resp.status_code == 200 and resp.json().get("status") == "ready"
        except Exception:
            return False
