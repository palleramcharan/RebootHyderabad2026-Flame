from __future__ import annotations

from typing import Any, Dict

EVENT_TYPE_MAP = {
    "SUBMISSION_CREATED": "CREATE",
    "SUBMISSION_UPDATED": "UPDATE",
    "SUBMISSION_DELETED": "DELETE",
    "SUBMISSION_VIEWED": "VIEW",
    "FILE_UPLOADED": "UPLOAD",
    "FILE_DOWNLOADED": "DOWNLOAD",
    "APPROVAL": "APPROVE",
    "REJECTION": "REJECT",
    "WORKFLOW_CHANGE": "TRANSITION",
    "STATUS_CHANGE": "STATUS_UPDATE",
    "VERIFICATION": "VERIFY",
    "SIGNATURE_ADDED": "SIGN",
}


def normalize_event(source: str, raw: Dict[str, Any]) -> Dict[str, Any]:
    event_type = raw.get("eventType", source)
    operation = EVENT_TYPE_MAP.get(event_type, event_type)

    return {
        "submissionId": raw.get("submissionId") or raw.get("submission_id", ""),
        "applicationId": raw.get("applicationId") or raw.get("application_id", ""),
        "service": raw.get("service", ""),
        "eventType": event_type,
        "operation": operation,
        "sha256Hash": raw.get("sha256Hash") or raw.get("sha256_hash", ""),
        "timestamp": raw.get("timestamp", ""),
        "userId": raw.get("userId") or raw.get("user_id", "SYSTEM"),
        "mspId": raw.get("mspId") or raw.get("msp_id", "Org1MSP"),
        "channelName": raw.get("channelName") or raw.get("channel_name", "auditchannel"),
        "correlationId": raw.get("correlationId") or raw.get("correlation_id", ""),
        "metadata": raw.get("metadata", raw.get("data", {})),
    }
