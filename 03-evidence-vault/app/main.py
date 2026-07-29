import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent
EVIDENCE_DIR = BASE_DIR / "data" / "evidence"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Evidence Vault", version="2.0.0")


class EvidenceStoreRequest(BaseModel):
    submissionId: str
    applicationId: str
    service: str
    businessEvent: str
    payload: Dict[str, Any]


class EvidenceVerifyRequest(BaseModel):
    evidenceHash: str


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _evidence_path(submission_id: str, version: int = 1) -> Path:
    return EVIDENCE_DIR / submission_id / f"v{version}.json"


def _index_path() -> Path:
    return EVIDENCE_DIR / "index.json"


def _load_index() -> Dict[str, Any]:
    p = _index_path()
    if p.exists():
        return json.loads(p.read_text("utf-8"))
    return {}


def _save_index(idx: Dict[str, Any]):
    _index_path().write_text(json.dumps(idx, indent=2), "utf-8")


@app.post("/evidence", status_code=201)
def store_evidence(req: EvidenceStoreRequest):
    idx = _load_index()
    sub_id = req.submissionId
    evidence_data = req.payload

    if sub_id in idx:
        version = idx[sub_id]["latestVersion"] + 1
    else:
        version = 1

    payload_bytes = json.dumps(evidence_data, sort_keys=True).encode("utf-8")
    evidence_hash = _sha256(payload_bytes)

    record = {
        "submissionId": sub_id,
        "applicationId": req.applicationId,
        "service": req.service,
        "businessEvent": req.businessEvent,
        "evidenceHash": evidence_hash,
        "version": version,
        "payload": evidence_data,
        "storedAt": datetime.now(timezone.utc).isoformat(),
    }

    sub_dir = EVIDENCE_DIR / sub_id
    sub_dir.mkdir(parents=True, exist_ok=True)
    (_evidence_path(sub_id, version)).write_text(json.dumps(record, indent=2), "utf-8")

    idx[sub_id] = {
        "applicationId": req.applicationId,
        "service": req.service,
        "businessEvent": req.businessEvent,
        "latestVersion": version,
        "latestHash": evidence_hash,
        "storedAt": record["storedAt"],
    }
    _save_index(idx)

    return {
        "submissionId": sub_id,
        "version": version,
        "evidenceHash": evidence_hash,
        "status": "stored",
        "storedAt": record["storedAt"],
    }


@app.get("/evidence/{submission_id}")
def get_evidence(submission_id: str, version: Optional[int] = None):
    idx = _load_index()
    if submission_id not in idx:
        raise HTTPException(404, f"Evidence not found: {submission_id}")

    if version is None:
        version = idx[submission_id]["latestVersion"]

    p = _evidence_path(submission_id, version)
    if not p.exists():
        raise HTTPException(404, f"Version {version} not found for {submission_id}")

    return json.loads(p.read_text("utf-8"))


@app.get("/evidence/{submission_id}/versions")
def list_versions(submission_id: str):
    sub_dir = EVIDENCE_DIR / submission_id
    if not sub_dir.exists():
        raise HTTPException(404, f"Evidence not found: {submission_id}")

    versions = []
    for f in sorted(sub_dir.glob("v*.json")):
        data = json.loads(f.read_text("utf-8"))
        versions.append({
            "version": data["version"],
            "evidenceHash": data["evidenceHash"],
            "storedAt": data["storedAt"],
        })
    return {"submissionId": submission_id, "versions": versions}


@app.post("/evidence/{submission_id}/verify")
def verify_evidence(submission_id: str, req: EvidenceVerifyRequest):
    idx = _load_index()
    if submission_id not in idx:
        raise HTTPException(404, f"Evidence not found: {submission_id}")

    p = _evidence_path(submission_id, idx[submission_id]["latestVersion"])
    if not p.exists():
        raise HTTPException(404, f"Evidence file missing for {submission_id}")

    data = json.loads(p.read_text("utf-8"))
    payload_bytes = json.dumps(data["payload"], sort_keys=True).encode("utf-8")
    computed_hash = _sha256(payload_bytes)

    match = computed_hash == req.evidenceHash
    return {
        "submissionId": submission_id,
        "verified": match,
        "computedHash": computed_hash,
        "providedHash": req.evidenceHash,
        "storedHash": data["evidenceHash"],
        "applicationId": data["applicationId"],
        "service": data["service"],
        "businessEvent": data["businessEvent"],
    }


@app.post("/evidence/{submission_id}/rebuild")
def rebuild_evidence(submission_id: str, payload: Dict[str, Any]):
    req = EvidenceStoreRequest(
        submissionId=submission_id,
        applicationId=payload.get("applicationId", ""),
        service=payload.get("service", ""),
        businessEvent=payload.get("businessEvent", ""),
        payload=payload,
    )
    return store_evidence(req)


@app.get("/evidence")
def list_all_evidence():
    idx = _load_index()
    results = []
    for sub_id, meta in idx.items():
        results.append({
            "submissionId": sub_id,
            "applicationId": meta["applicationId"],
            "service": meta["service"],
            "businessEvent": meta["businessEvent"],
            "latestVersion": meta["latestVersion"],
            "latestHash": meta["latestHash"],
            "storedAt": meta["storedAt"],
        })
    return results


@app.get("/health/live")
def health_live():
    return {"status": "alive", "service": "evidence-vault", "version": "2.0.0"}


@app.get("/health/ready")
def health_ready():
    return {"status": "ready", "evidenceCount": len(_load_index())}


@app.get("/health")
def health():
    idx = _load_index()
    return {
        "status": "ready",
        "service": "evidence-vault",
        "version": "2.0.0",
        "evidenceCount": len(idx),
    }
