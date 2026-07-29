from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class FabricConnector(ABC):
    @abstractmethod
    def submit_audit_event(self, audit_event: Dict[str, Any]) -> Dict[str, Any]:
        ...

    @abstractmethod
    def get_application_audit_history(self, application_id: str) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def verify_on_ledger(self, event_key: str, expected_hash: Optional[str] = None) -> Dict[str, Any]:
        ...

    @abstractmethod
    def is_adapter_ready(self) -> bool:
        ...
