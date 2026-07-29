from __future__ import annotations

import httpx
from typing import Any, Dict, Optional

GATEWAY_BASE_URL = "http://localhost:3000"


async def verify_on_ledger(event_key: str, gateway_url: Optional[str] = None) -> Dict[str, Any]:
    url = f"{gateway_url or GATEWAY_BASE_URL}/audit/verify/{event_key}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()


async def verify_on_ledger_with_hash(
    event_key: str,
    expected_hash: str,
    gateway_url: Optional[str] = None,
) -> Dict[str, Any]:
    url = f"{gateway_url or GATEWAY_BASE_URL}/audit/verify/{event_key}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params={"expectedHash": expected_hash})
        resp.raise_for_status()
        return resp.json()
