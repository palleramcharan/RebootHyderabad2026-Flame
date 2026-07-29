import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "07-block-indexer" / "app"))
from mongo_client import MongoStore

BASE_DIR = Path(__file__).resolve().parent.parent

app = FastAPI(title="Audit Ledger Dashboard API", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

mongo = MongoStore()


@app.get("/", response_class=HTMLResponse)
def index():
    return (BASE_DIR / "dashboard.html").read_text("utf-8")


@app.get("/api/events")
def get_events(
    application_id: Optional[str] = None,
    service: Optional[str] = None,
    business_event: Optional[str] = None,
    user_id: Optional[str] = None,
    event_severity: Optional[str] = None,
    workflow_step: Optional[str] = None,
    correlation_id: Optional[str] = None,
    audit_id: Optional[str] = None,
    transaction_id: Optional[str] = None,
    block_number: Optional[int] = None,
    limit: int = Query(100, le=5000),
    offset: int = Query(0, ge=0),
):
    filter_query = {}
    if application_id:
        filter_query["applicationId"] = application_id
    if service:
        filter_query["service"] = service
    if business_event:
        filter_query["businessEvent"] = business_event
    if user_id:
        filter_query["userId"] = user_id
    if event_severity:
        filter_query["eventSeverity"] = event_severity
    if workflow_step:
        filter_query["workflowStep"] = workflow_step
    if correlation_id:
        filter_query["correlationId"] = correlation_id
    if audit_id:
        filter_query["auditId"] = audit_id
    if transaction_id:
        filter_query["transactionId"] = transaction_id
    if block_number is not None:
        filter_query["blockNumber"] = block_number

    docs = mongo.audit_events.find(filter_query, {"_id": 0}).sort("timestamp", -1).skip(offset).limit(limit)
    return list(docs)


@app.get("/api/events/{event_key}")
def get_event(event_key: str):
    doc = mongo.audit_events.find_one({"eventKey": event_key}, {"_id": 0})
    if not doc:
        raise HTTPException(404, f"Event not found: {event_key}")
    return doc


@app.get("/api/applications")
def list_applications():
    docs = mongo.application_timelines.find({}, {"_id": 0}).sort("latestTimestamp", -1)
    return list(docs)


@app.get("/api/applications/{application_id}")
def get_application(application_id: str):
    doc = mongo.application_timelines.find_one({"applicationId": application_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, f"Application not found: {application_id}")
    return doc


@app.get("/api/applications/{application_id}/timeline")
def get_application_timeline(application_id: str):
    events = list(mongo.audit_events.find(
        {"applicationId": application_id},
        {"_id": 0},
    ).sort("sequence", 1))
    if not events:
        raise HTTPException(404, f"No events found for application: {application_id}")
    return events


@app.get("/api/applications/{application_id}/field-changes")
def get_field_changes(application_id: str):
    changes = list(mongo.field_changes.find(
        {"applicationId": application_id},
        {"_id": 0},
    ).sort("timestamp", -1))
    return changes


@app.get("/api/field-changes")
def get_all_field_changes(limit: int = 100):
    changes = list(mongo.field_changes.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit))
    return changes


@app.get("/api/blockchain/blocks")
def get_blocks(limit: int = 50):
    blocks = list(mongo.block_metadata.find({}, {"_id": 0}).sort("blockNumber", -1).limit(limit))
    return blocks


@app.get("/api/blockchain/metrics")
def get_metrics():
    metrics = {}
    docs = mongo.blockchain_metrics.find({}, {"_id": 0})
    for doc in docs:
        metrics[doc["metric"]] = doc.get("value")
    return metrics


@app.get("/api/blockchain/statistics")
def get_statistics():
    total_events = mongo.audit_events.count_documents({})
    total_apps = mongo.application_timelines.count_documents({})
    total_changes = mongo.field_changes.count_documents({})
    total_blocks = mongo.block_metadata.count_documents({})

    by_service = list(mongo.audit_events.aggregate([
        {"$group": {"_id": "$service", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]))
    by_severity = list(mongo.audit_events.aggregate([
        {"$group": {"_id": "$eventSeverity", "count": {"$sum": 1}}},
    ]))
    by_category = list(mongo.audit_events.aggregate([
        {"$group": {"_id": "$eventCategory", "count": {"$sum": 1}}},
    ]))

    service_counts = {s["_id"]: s["count"] for s in by_service}
    severity_counts = {s["_id"]: s["count"] for s in by_severity}
    category_counts = {s["_id"]: s["count"] for s in by_category}

    return {
        "totalEvents": total_events,
        "totalApplications": total_apps,
        "totalFieldChanges": total_changes,
        "totalBlocks": total_blocks,
        "byService": service_counts,
        "bySeverity": severity_counts,
        "byCategory": category_counts,
    }


@app.get("/api/integrity/checks")
def get_integrity_checks(limit: int = 20):
    checks = list(mongo.integrity_checks.find({}, {"_id": 0}).sort("checkedAt", -1).limit(limit))
    return checks


@app.get("/api/integrity/application/{application_id}")
def check_application_integrity(application_id: str):
    events = list(mongo.audit_events.find(
        {"applicationId": application_id},
        {"_id": 0},
    ).sort("sequence", 1))

    if not events:
        return {"applicationId": application_id, "chainIntact": True, "eventCount": 0, "entries": []}

    import hashlib
    entries = []
    chain_intact = True

    for i, evt in enumerate(events):
        expected_prev = events[i - 1].get("currentHash", "") if i > 0 else ""
        prev_match = evt.get("previousHash", "") == expected_prev

        hash_input = "|".join([
            evt.get("applicationId", ""),
            evt.get("businessEvent", ""),
            evt.get("timestamp", ""),
            evt.get("evidenceHash", ""),
            evt.get("previousHash", ""),
            evt.get("correlationId", ""),
            json.dumps(evt.get("changedFields", []), sort_keys=True, separators=(',', ':')),
            str(evt.get("sequence", 0)),
        ])
        computed = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()
        hash_match = computed == evt.get("currentHash", "")

        if not prev_match or not hash_match:
            chain_intact = False

        entries.append({
            "sequence": evt.get("sequence"),
            "auditId": evt.get("auditId"),
            "previousHashMatch": prev_match,
            "currentHashMatch": hash_match,
        })

    return {
        "applicationId": application_id,
        "chainIntact": chain_intact,
        "eventCount": len(events),
        "entries": entries,
    }


@app.get("/api/search")
def search(q: str = Query("", min_length=1), limit: int = Query(50, le=200)):
    if not q:
        return []

    results = list(mongo.audit_events.find(
        {"$text": {"$search": q}},
        {"_id": 0},
    ).limit(limit))

    if not results:
        results = list(mongo.audit_events.find(
            {"$or": [
                {"auditId": {"$regex": q, "$options": "i"}},
                {"applicationId": {"$regex": q, "$options": "i"}},
                {"correlationId": {"$regex": q, "$options": "i"}},
                {"transactionId": {"$regex": q, "$options": "i"}},
                {"eventKey": {"$regex": q, "$options": "i"}},
                {"service": {"$regex": q, "$options": "i"}},
                {"businessEvent": {"$regex": q, "$options": "i"}},
                {"userId": {"$regex": q, "$options": "i"}},
                {"submissionId": {"$regex": q, "$options": "i"}},
            ]},
            {"_id": 0},
        ).limit(limit))

    return results


@app.get("/api/health")
def health():
    return {
        "status": "ready",
        "service": "audit-dashboard",
        "version": "2.0.0",
        "mongoConnected": True,
        "eventCount": mongo.audit_events.count_documents({}),
    }
