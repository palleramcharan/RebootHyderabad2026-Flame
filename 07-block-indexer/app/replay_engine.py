import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from mongo_client import MongoStore

logger = logging.getLogger("replay_engine")

FABRIC_ADAPTER_URL = "http://localhost:8080"


class AuditReplayEngine:
    def __init__(self, adapter_url: str = FABRIC_ADAPTER_URL, mongo: Optional[MongoStore] = None):
        self.adapter_url = adapter_url.rstrip("/")
        self.mongo = mongo or MongoStore()

    def _fetch_application_events(self, application_id: str) -> List[Dict[str, Any]]:
        resp = httpx.get(f"{self.adapter_url}/audit/applications/{application_id}/events", timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _fetch_all_events(self) -> List[Dict[str, Any]]:
        resp = httpx.get(f"{self.adapter_url}/audit/events", timeout=30)
        resp.raise_for_status()
        return resp.json()

    def replay_complete_lifecycle(self, application_id: str) -> Dict[str, Any]:
        events = self._fetch_application_events(application_id)
        events.sort(key=lambda e: e.get("sequence", 0))
        return self._build_replay_result(application_id, events)

    def replay_until_timestamp(self, application_id: str, timestamp: str) -> Dict[str, Any]:
        events = self._fetch_application_events(application_id)
        events.sort(key=lambda e: e.get("sequence", 0))
        cutoff = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        filtered = []
        for e in events:
            evt_ts = datetime.fromisoformat(e.get("timestamp", "").replace("Z", "+00:00"))
            if evt_ts <= cutoff:
                filtered.append(e)
        return self._build_replay_result(application_id, filtered)

    def replay_until_block(self, application_id: str, block_number: int) -> Dict[str, Any]:
        events = self._fetch_application_events(application_id)
        events.sort(key=lambda e: e.get("sequence", 0))
        filtered = [e for e in events if e.get("blockNumber", 0) <= block_number]
        return self._build_replay_result(application_id, filtered)

    def replay_until_transaction(self, application_id: str, transaction_id: str) -> Dict[str, Any]:
        events = self._fetch_application_events(application_id)
        events.sort(key=lambda e: e.get("sequence", 0))
        filtered = []
        for e in events:
            filtered.append(e)
            if e.get("transactionId") == transaction_id:
                break
        return self._build_replay_result(application_id, filtered)

    def compare_versions(self, application_id: str, version1_event_key: str, version2_event_key: str) -> Dict[str, Any]:
        events = self._fetch_application_events(application_id)
        events.sort(key=lambda e: e.get("sequence", 0))

        state1 = {}
        state2 = {}
        idx1 = None
        idx2 = None

        for i, e in enumerate(events):
            if e.get("eventKey") == version1_event_key:
                idx1 = i
            if e.get("eventKey") == version2_event_key:
                idx2 = i

        for i, e in enumerate(events):
            if idx1 is not None and i <= idx1:
                self._apply_event(state1, e)
            if idx2 is not None and i <= idx2:
                self._apply_event(state2, e)

        differences = []
        all_keys = set(list(state1.keys()) + list(state2.keys()))
        for key in all_keys:
            v1 = state1.get(key)
            v2 = state2.get(key)
            if v1 != v2:
                differences.append({"field": key, "version1Value": v1, "version2Value": v2})

        return {
            "applicationId": application_id,
            "version1EventKey": version1_event_key,
            "version2EventKey": version2_event_key,
            "stateVersion1": state1,
            "stateVersion2": state2,
            "differences": differences,
            "differenceCount": len(differences),
        }

    def point_in_time_reconstruction(self, application_id: str, timestamp: str) -> Dict[str, Any]:
        return self.replay_until_timestamp(application_id, timestamp)

    def _build_replay_result(self, application_id: str, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        reconstructed_state = {}
        timeline = []

        for i, evt in enumerate(events):
            self._apply_event(reconstructed_state, evt)
            timeline.append({
                "sequence": evt.get("sequence"),
                "auditId": evt.get("auditId"),
                "businessEvent": evt.get("businessEvent"),
                "service": evt.get("service"),
                "workflowStep": evt.get("workflowStep"),
                "timestamp": evt.get("timestamp"),
                "eventKey": evt.get("eventKey"),
                "transactionId": evt.get("transactionId"),
                "blockNumber": evt.get("blockNumber"),
                "currentHash": evt.get("currentHash"),
                "previousHash": evt.get("previousHash"),
                "changedFields": evt.get("changedFields", []),
            })

        latest = events[-1] if events else {}
        return {
            "applicationId": application_id,
            "totalEvents": len(events),
            "reconstructedState": reconstructed_state,
            "currentService": latest.get("service", ""),
            "currentStep": latest.get("workflowStep", ""),
            "latestTimestamp": latest.get("timestamp", ""),
            "timeline": timeline,
        }

    def _apply_event(self, state: Dict[str, Any], event: Dict[str, Any]):
        changed_fields = event.get("changedFields", [])
        if changed_fields:
            for change in changed_fields:
                field = change.get("field")
                new_value = change.get("newValue")
                if field:
                    state[field] = new_value

        metadata = event.get("metadata", {})
        if isinstance(metadata, dict) and "payload" in metadata:
            payload = metadata["payload"]
            if isinstance(payload, dict):
                for k, v in payload.items():
                    if k not in state:
                        state[k] = v

    def rebuild_all_applications(self) -> Dict[str, Any]:
        events = self._fetch_all_events()
        apps: Dict[str, List[Dict]] = {}
        for e in events:
            app_id = e.get("applicationId", "unknown")
            apps.setdefault(app_id, []).append(e)

        results = {}
        for app_id, app_events in apps.items():
            app_events.sort(key=lambda e: e.get("sequence", 0))
            results[app_id] = self._build_replay_result(app_id, app_events)
        return results
