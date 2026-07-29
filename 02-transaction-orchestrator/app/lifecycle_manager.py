from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "state"
STATE_DIR.mkdir(parents=True, exist_ok=True)

LIFECYCLE: Dict[str, Dict] = {
    "ai_recommendation":{"tx": "TX001", "seq": 1, "next": "human_override",  "label": "AI Recommendation"},
    "human_override":  {"tx": "TX002", "seq": 2, "next": "bdss",             "label": "Human Override"},
    "bdss":            {"tx": "TX003", "seq": 3, "next": "crss",             "label": "Business Decision Support"},
    "crss":            {"tx": "TX004", "seq": 4, "next": "credit_approval",  "label": "Credit Risk Scoring"},
    "credit_approval": {"tx": "TX005", "seq": 5, "next": "iris",             "label": "Credit Approval"},
    "iris":            {"tx": "TX006", "seq": 6, "next": None,               "label": "IRIS Booking"},
}

TX_TO_SERVICE = {v["tx"]: k for k, v in LIFECYCLE.items()}
SERVICE_TO_TX = {k: v["tx"] for k, v in LIFECYCLE.items()}


class LifecycleManager:
    def __init__(self):
        self._state: Dict[str, Dict] = {}
        self._load_all()

    def _state_path(self, application_id: str) -> Path:
        return STATE_DIR / f"{application_id}.json"

    def _load_all(self):
        for f in STATE_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                self._state[data["application_id"]] = data
            except (json.JSONDecodeError, KeyError):
                continue

    def _persist(self, application_id: str):
        if application_id in self._state:
            self._state_path(application_id).write_text(
                json.dumps(self._state[application_id], indent=2), encoding="utf-8"
            )

    def get_current_state(self, application_id: str) -> Optional[Dict]:
        return self._state.get(application_id)

    def get_current_step(self, application_id: str) -> Optional[str]:
        state = self._state.get(application_id)
        return state.get("current_step") if state else None

    def get_next_step(self, application_id: str) -> Optional[str]:
        current = self.get_current_step(application_id)
        if not current:
            return list(LIFECYCLE.keys())[0]
        step_info = LIFECYCLE.get(current)
        return step_info["next"] if step_info else None

    def get_next_tx(self, application_id: str) -> Optional[str]:
        next_step = self.get_next_step(application_id)
        return SERVICE_TO_TX.get(next_step) if next_step else None

    def get_step_info(self, step: str) -> Optional[Dict]:
        return LIFECYCLE.get(step)

    def get_tx_info(self, tx: str) -> Optional[Dict]:
        service = TX_TO_SERVICE.get(tx)
        if not service:
            return None
        return {**LIFECYCLE[service], "service": service}

    def validate_transition(self, application_id: str, target_step: str) -> Dict:
        state = self._state.get(application_id)
        current_step = state.get("current_step") if state else None

        if current_step is None:
            first_step = list(LIFECYCLE.keys())[0]
            if target_step == first_step:
                return {"valid": True, "message": "Initial transaction permitted"}
            return {"valid": False, "message": f"First transaction must be {first_step} (TX001), not {target_step}"}

        step_info = LIFECYCLE.get(current_step)
        expected_next = step_info["next"] if step_info else None

        if expected_next is None:
            return {"valid": False, "message": f"Application {application_id} is already completed"}

        if target_step == expected_next:
            return {"valid": True, "message": f"Transition {current_step} -> {target_step} permitted"}

        return {
            "valid": False,
            "message": (
                f"Invalid transition. Current: {current_step} ({step_info['tx']}). "
                f"Expected next: {expected_next} ({SERVICE_TO_TX.get(expected_next, 'N/A')}). Got: {target_step}"
            ),
        }

    def advance(self, application_id: str, step: str) -> Dict:
        validation = self.validate_transition(application_id, step)
        if not validation["valid"]:
            return validation

        if application_id not in self._state:
            self._state[application_id] = {
                "application_id": application_id,
                "current_step": step,
                "history": [],
                "completed": False,
            }

        state = self._state[application_id]
        state["history"].append({
            "step": step,
            "tx": SERVICE_TO_TX.get(step),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        state["current_step"] = step

        step_info = LIFECYCLE.get(step)
        if step_info and step_info["next"] is None:
            state["completed"] = True

        self._persist(application_id)
        return {"valid": True, "message": f"Advanced to {step} ({SERVICE_TO_TX.get(step)})", "state": state}

    def get_lifecycle_summary(self, application_id: str) -> Dict:
        state = self._state.get(application_id)
        first_step = list(LIFECYCLE.keys())[0]
        if not state:
            return {
                "application_id": application_id,
                "status": "not_started",
                "current_step": None,
                "current_tx": None,
                "next_step": first_step,
                "next_tx": "TX001",
                "completed": False,
                "history": [],
            }
        return {
            "application_id": application_id,
            "status": "completed" if state["completed"] else "in_progress",
            "current_step": state["current_step"],
            "current_tx": SERVICE_TO_TX.get(state["current_step"]),
            "next_step": self.get_next_step(application_id),
            "next_tx": self.get_next_tx(application_id),
            "completed": state["completed"],
            "history": state["history"],
        }

    def reset(self, application_id: str):
        self._state.pop(application_id, None)
        p = self._state_path(application_id)
        if p.exists():
            p.unlink()
