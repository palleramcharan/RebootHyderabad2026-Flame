import os
import httpx

FABRIC_ADAPTER_URL = os.getenv("FABRIC_ADAPTER_URL", "http://localhost:8080")


class FabricClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or FABRIC_ADAPTER_URL).rstrip("/")

    def get_all_events(self) -> list[dict]:
        resp = httpx.get(f"{self.base_url}/audit/events", timeout=30)
        resp.raise_for_status()
        return resp.json()

    def get_event(self, event_key: str) -> dict:
        resp = httpx.get(f"{self.base_url}/audit/events/{event_key}", timeout=15)
        resp.raise_for_status()
        return resp.json()

    def health(self) -> dict:
        resp = httpx.get(f"{self.base_url}/health/live", timeout=5)
        resp.raise_for_status()
        return resp.json()
