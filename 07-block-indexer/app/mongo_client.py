import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pymongo import MongoClient, ASCENDING, DESCENDING, TEXT
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "audit_ledger")


class MongoStore:
    def __init__(self, uri: str = None, db_name: str = None):
        self.client = MongoClient(uri or MONGO_URI)
        self.db = self.client[db_name or MONGO_DB]
        self._init_collections()

    def _init_collections(self):
        self.audit_events: Collection = self.db["audit_events"]
        self.application_timelines: Collection = self.db["application_timelines"]
        self.field_changes: Collection = self.db["field_changes"]
        self.block_metadata: Collection = self.db["block_metadata"]
        self.integrity_checks: Collection = self.db["integrity_checks"]
        self.blockchain_metrics: Collection = self.db["blockchain_metrics"]
        self._ensure_indexes()

    def _ensure_indexes(self):
        self.audit_events.create_index([("eventKey", ASCENDING)], unique=True)
        self.audit_events.create_index([("auditId", ASCENDING)])
        self.audit_events.create_index([("applicationId", ASCENDING)])
        self.audit_events.create_index([("correlationId", ASCENDING)])
        self.audit_events.create_index([("transactionId", ASCENDING)])
        self.audit_events.create_index([("blockNumber", ASCENDING)])
        self.audit_events.create_index([("businessEvent", ASCENDING)])
        self.audit_events.create_index([("service", ASCENDING)])
        self.audit_events.create_index([("timestamp", DESCENDING)])
        self.audit_events.create_index([("userId", ASCENDING)])
        self.audit_events.create_index([("eventSeverity", ASCENDING)])
        self.audit_events.create_index([("workflowStep", ASCENDING)])
        self.audit_events.create_index([("sequence", ASCENDING)])

        self.application_timelines.create_index([("applicationId", ASCENDING)], unique=True)
        self.application_timelines.create_index([("latestTimestamp", DESCENDING)])

        self.field_changes.create_index([("applicationId", ASCENDING)])
        self.field_changes.create_index([("auditId", ASCENDING)])
        self.field_changes.create_index([("timestamp", DESCENDING)])

        self.block_metadata.create_index([("blockNumber", ASCENDING)], unique=True)
        self.block_metadata.create_index([("timestamp", DESCENDING)])

        self.integrity_checks.create_index([("applicationId", ASCENDING)])
        self.integrity_checks.create_index([("checkedAt", DESCENDING)])

        self.blockchain_metrics.create_index([("metric", ASCENDING)])
        self.blockchain_metrics.create_index([("recordedAt", DESCENDING)])

    def upsert_audit_event(self, event: dict) -> bool:
        event_key = event.get("eventKey", "")
        if not event_key:
            return False
        event["exportedAt"] = datetime.now(timezone.utc).isoformat()
        try:
            self.audit_events.update_one(
                {"eventKey": event_key},
                {"$set": event},
                upsert=True,
            )
            return True
        except DuplicateKeyError:
            return False

    def upsert_application_timeline(self, application_id: str, events: List[dict]):
        steps = []
        for evt in events:
            steps.append({
                "auditId": evt.get("auditId"),
                "businessEvent": evt.get("businessEvent"),
                "workflowStep": evt.get("workflowStep"),
                "service": evt.get("service"),
                "timestamp": evt.get("timestamp"),
                "sequence": evt.get("sequence"),
                "eventKey": evt.get("eventKey"),
            })
        latest = events[-1] if events else {}
        self.application_timelines.update_one(
            {"applicationId": application_id},
            {"$set": {
                "applicationId": application_id,
                "totalEvents": len(events),
                "currentStep": latest.get("workflowStep", ""),
                "currentService": latest.get("service", ""),
                "latestTimestamp": latest.get("timestamp", ""),
                "latestHash": latest.get("currentHash", ""),
                "steps": steps,
                "updatedAt": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True,
        )

    def upsert_field_change(self, change: dict):
        self.field_changes.update_one(
            {"auditId": change.get("auditId"), "field": change.get("field")},
            {"$set": {
                **change,
                "exportedAt": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True,
        )

    def upsert_block_metadata(self, block_info: dict):
        block_num = block_info.get("blockNumber")
        if block_num is None:
            return
        self.block_metadata.update_one(
            {"blockNumber": block_num},
            {"$set": {
                **block_info,
                "exportedAt": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True,
        )

    def upsert_integrity_check(self, application_id: str, result: dict):
        self.integrity_checks.update_one(
            {"applicationId": application_id, "checkedAt": result.get("checkedAt", "")},
            {"$set": {
                **result,
                "exportedAt": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True,
        )

    def upsert_metric(self, name: str, value: Any, labels: dict = None):
        self.blockchain_metrics.update_one(
            {"metric": name},
            {"$set": {
                "metric": name,
                "value": value,
                "labels": labels or {},
                "recordedAt": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True,
        )

    def get_indexed_event_keys(self) -> set:
        docs = self.audit_events.find({}, {"eventKey": 1, "_id": 0})
        return {d["eventKey"] for d in docs}

    def get_event_count(self) -> int:
        return self.audit_events.count_documents({})

    def get_all_events(self, limit: int = 5000, skip: int = 0) -> list:
        docs = self.audit_events.find({}, {"_id": 0}).sort("timestamp", -1).skip(skip).limit(limit)
        return list(docs)

    def query_events(self, filter_query: dict, limit: int = 100) -> list:
        docs = self.audit_events.find(filter_query, {"_id": 0}).sort("timestamp", -1).limit(limit)
        return list(docs)

    def rebuild_application_timelines(self):
        pipeline = [
            {"$sort": {"sequence": 1}},
            {"$group": {
                "_id": "$applicationId",
                "events": {"$push": {
                    "auditId": "$auditId",
                    "businessEvent": "$businessEvent",
                    "workflowStep": "$workflowStep",
                    "service": "$service",
                    "timestamp": "$timestamp",
                    "sequence": "$sequence",
                    "eventKey": "$eventKey",
                    "currentHash": "$currentHash",
                }},
                "count": {"$sum": 1},
                "latestTimestamp": {"$max": "$timestamp"},
            }}
        ]
        results = self.audit_events.aggregate(pipeline)
        for r in results:
            app_id = r["_id"]
            events = r["events"]
            latest = events[-1] if events else {}
            self.application_timelines.update_one(
                {"applicationId": app_id},
                {"$set": {
                    "applicationId": app_id,
                    "totalEvents": r["count"],
                    "currentStep": latest.get("workflowStep", ""),
                    "currentService": latest.get("service", ""),
                    "latestTimestamp": r["latestTimestamp"],
                    "latestHash": latest.get("currentHash", ""),
                    "steps": events,
                    "updatedAt": datetime.now(timezone.utc).isoformat(),
                }},
                upsert=True,
            )

    def rebuild_field_changes(self):
        self.field_changes.delete_many({})
        events = self.audit_events.find({"changedFields": {"$exists": True, "$ne": []}}, {"_id": 0})
        for evt in events:
            for change in evt.get("changedFields", []):
                self.upsert_field_change({
                    "auditId": evt.get("auditId"),
                    "applicationId": evt.get("applicationId"),
                    "correlationId": evt.get("correlationId"),
                    "businessEvent": evt.get("businessEvent"),
                    "service": evt.get("service"),
                    "timestamp": evt.get("timestamp"),
                    "field": change.get("field"),
                    "oldValue": change.get("oldValue"),
                    "newValue": change.get("newValue"),
                    "eventKey": evt.get("eventKey"),
                    "transactionId": evt.get("transactionId"),
                })

    def close(self):
        self.client.close()
