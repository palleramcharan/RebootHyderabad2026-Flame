from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


def build_audit_event(
    submission_id: str,
    application_id: str,
    service: str,
    sha256_hash: str,
    event_type: str = "SUBMISSION_CREATED",
    operation: str = "CREATE",
    user_id: str = "SYSTEM",
    msp_id: str = "Org1MSP",
    channel_name: str = "auditchannel",
    correlation_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "submissionId": submission_id,
        "applicationId": application_id,
        "service": service,
        "eventType": event_type,
        "operation": operation,
        "sha256Hash": sha256_hash,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "userId": user_id,
        "mspId": msp_id,
        "channelName": channel_name,
        "correlationId": correlation_id or "",
        "metadata": metadata or {},
    }


def build_from_submission_record(record: Dict[str, Any], sha256_hash: str) -> Dict[str, Any]:
    return build_audit_event(
        submission_id=record.get("submission_id", ""),
        application_id=record.get("application_id", ""),
        service=record.get("service", ""),
        sha256_hash=sha256_hash,
        event_type="SUBMISSION_CREATED",
        operation="CREATE",
        user_id="SYSTEM",
    )
