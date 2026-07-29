from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent.parent
BUSINESS_SERVICES = BASE_DIR / "01-business-services"

ORCHESTRATOR_APP = BASE_DIR / "02-transaction-orchestrator" / "app"
sys.path.insert(0, str(ORCHESTRATOR_APP))

from transaction_queue import TransactionQueue, SERVICE_TX_MAP

_queue = TransactionQueue()

SERVICE_DIRS = {
    "ai_recommendation": BUSINESS_SERVICES / "01-ai-recommendation-engine" / "submissions",
    "human_override": BUSINESS_SERVICES / "02-human-override" / "submissions",
    "bdss": BUSINESS_SERVICES / "03-bdss" / "submissions",
    "crss": BUSINESS_SERVICES / "04-crss" / "submissions",
    "credit_approval": BUSINESS_SERVICES / "05-credit-approval" / "submissions",
    "iris": BUSINESS_SERVICES / "06-iris" / "submissions",
}

for d in SERVICE_DIRS.values():
    d.mkdir(parents=True, exist_ok=True)

APPLICATIONS = [
    {"id": "APP-1001", "name": "Home Loan", "max_amount": 10_000_000},
    {"id": "APP-1002", "name": "Personal Loan", "max_amount": 2_500_000},
    {"id": "APP-1003", "name": "Vehicle Loan", "max_amount": 5_000_000},
    {"id": "APP-1004", "name": "Education Loan", "max_amount": 4_000_000},
    {"id": "APP-1005", "name": "Business Loan", "max_amount": 20_000_000},
    {"id": "APP-1006", "name": "Gold Loan", "max_amount": 3_000_000},
    {"id": "APP-1007", "name": "Mortgage Loan", "max_amount": 50_000_000},
    {"id": "APP-1008", "name": "Working Capital", "max_amount": 15_000_000},
    {"id": "APP-1009", "name": "Equipment Financing", "max_amount": 8_000_000},
    {"id": "APP-1010", "name": "Trade Finance", "max_amount": 25_000_000},
]

SERVICE_INFO = {
    "ai_recommendation": {"name": "AI Recommendation", "label": "AI Recommendation Engine", "tx": "TX001", "step": "01"},
    "human_override": {"name": "Human Override", "label": "Human Override & Exception Mgmt", "tx": "TX002", "step": "02"},
    "bdss": {"name": "BDSS", "label": "Business Decision Support System", "tx": "TX003", "step": "03"},
    "crss": {"name": "CRSS", "label": "Credit Risk Scoring Service", "tx": "TX004", "step": "04"},
    "credit_approval": {"name": "Credit Approval", "label": "Final Executive Sign-off", "tx": "TX005", "step": "05"},
    "iris": {"name": "IRIS", "label": "Booking & Core Banking Integration", "tx": "TX006", "step": "06"},
}

SERVICE_FORMS = {
    "ai_recommendation": [
        {"name": "risk_category", "label": "Assigned Risk Category", "type": "select", "options": ["Low", "Medium", "High", "Critical"], "required": True},
        {"name": "recommended_amount", "label": "Recommended Amount (₹)", "type": "number", "required": True},
        {"name": "confidence_score", "label": "Confidence Score (0-100)", "type": "number", "required": True},
        {"name": "reasoning", "label": "AI Reasoning", "type": "textarea", "required": True},
        {"name": "model_version", "label": "Model Version", "type": "text", "required": False},
    ],
    "human_override": [
        {"name": "override_reason", "label": "Override Reason", "type": "select", "options": ["Policy exception", "Customer relationship", "Collateral available", "Manual override", "Other"], "required": True},
        {"name": "modified_amount", "label": "Modified Amount (₹)", "type": "number", "required": False},
        {"name": "reviewer_name", "label": "Reviewer Name", "type": "text", "required": True},
        {"name": "reviewer_notes", "label": "Reviewer Notes", "type": "textarea", "required": True},
        {"name": "exception_approved", "label": "Exception Approved", "type": "select", "options": ["Yes", "No"], "required": True},
    ],
    "bdss": [
        {"name": "applicant_name", "label": "Applicant Name", "type": "text", "required": True},
        {"name": "email", "label": "Email", "type": "email", "required": True},
        {"name": "phone", "label": "Phone", "type": "text", "required": True},
        {"name": "annual_income", "label": "Annual Income (₹)", "type": "number", "required": True},
        {"name": "requested_amount", "label": "Requested Amount (₹)", "type": "number", "required": True},
        {"name": "employment_type", "label": "Employment Type", "type": "select", "options": ["Salaried", "Self-employed", "Business owner", "Student", "Retired"], "required": True},
        {"name": "purpose", "label": "Loan Purpose", "type": "textarea", "required": True},
    ],
    "crss": [
        {"name": "credit_score", "label": "Credit Score (300-900)", "type": "number", "required": True},
        {"name": "existing_loans", "label": "Existing Loans Count", "type": "number", "required": True},
        {"name": "default_history", "label": "Default History", "type": "select", "options": ["None", "30 days", "60 days", "90+ days"], "required": True},
        {"name": "dti_ratio", "label": "Debt-to-Income Ratio (%)", "type": "number", "required": True},
        {"name": "risk_category", "label": "Risk Category", "type": "select", "options": ["Low", "Medium", "High", "Critical"], "required": False},
    ],
    "credit_approval": [
        {"name": "approved_amount", "label": "Approved Amount (₹)", "type": "number", "required": True},
        {"name": "approval_conditions", "label": "Approval Conditions", "type": "textarea", "required": False},
        {"name": "officer_name", "label": "Approving Officer", "type": "text", "required": True},
        {"name": "officer_id", "label": "Officer ID", "type": "text", "required": True},
        {"name": "interest_rate", "label": "Interest Rate (%)", "type": "number", "required": True},
    ],
    "iris": [
        {"name": "account_number", "label": "Disbursement Account", "type": "text", "required": True},
        {"name": "disbursement_amount", "label": "Disbursement Amount (₹)", "type": "number", "required": True},
        {"name": "loan_tenure", "label": "Loan Tenure (months)", "type": "number", "required": True},
        {"name": "interest_rate", "label": "Final Interest Rate (%)", "type": "number", "required": True},
        {"name": "booking_date", "label": "Booking Date", "type": "date", "required": True},
        {"name": "status", "label": "Booking Status", "type": "select", "options": ["Booked", "Pending", "Failed"], "required": True},
    ],
}

USERS = [
    {
        "id": "USR-001", "name": "Rajesh Kumar",
        "ai_recommendation": {"risk_category": "Low", "recommended_amount": 4500000, "confidence_score": 92, "reasoning": "Strong repayment history, stable employment with 8 years tenure, low DTI ratio, excellent credit score of 780 indicates minimal default risk. Recommendation aligns with standard lending criteria.", "model_version": "AI-CR-v3.2.1"},
        "human_override": {"override_reason": "Policy exception", "modified_amount": 5000000, "reviewer_name": "Priya Sharma", "reviewer_notes": "Customer is a premium banking relationship holder with 12-year history. Exception approved based on collateral value and relationship depth. Monthly average balance consistently above 5L.", "exception_approved": "Yes"},
        "bdss": {"applicant_name": "Rajesh Kumar", "email": "rajesh.kumar@email.com", "phone": "9876543210", "annual_income": 1800000, "requested_amount": 5000000, "employment_type": "Salaried", "purpose": "Home renovation and extension"},
        "crss": {"credit_score": 780, "existing_loans": 2, "default_history": "None", "dti_ratio": 32, "risk_category": "Low"},
        "credit_approval": {"approved_amount": 5000000, "approval_conditions": "Property valuation report within 90 days, life insurance assignment, auto-debit mandate setup. Disbursement in 2 tranches of 30L and 20L upon completion of stages.", "officer_name": "Amit Verma", "officer_id": "AV-2024-0421", "interest_rate": 8.95},
        "iris": {"account_number": "HDFC00012345678", "disbursement_amount": 5000000, "loan_tenure": 240, "interest_rate": 8.95, "booking_date": "2026-08-15", "status": "Booked"},
    },
    {
        "id": "USR-002", "name": "Sneha Patel",
        "ai_recommendation": {"risk_category": "Medium", "recommended_amount": 1200000, "confidence_score": 78, "reasoning": "Self-employed with 5 years in business, moderate credit score, one prior 30-day default. DTI ratio at 45% is elevated. Business cash flows appear stable but require verification. Recommend conservative approach.", "model_version": "AI-CR-v3.2.1"},
        "human_override": {"override_reason": "Customer relationship", "modified_amount": 1500000, "reviewer_name": "Vikram Singh", "reviewer_notes": "Existing term deposit of 8L held with bank. Business GST returns show consistent upward trend. Approved under mid-corporate relationship program with additional collateral.", "exception_approved": "Yes"},
        "bdss": {"applicant_name": "Sneha Patel", "email": "sneha.patel@email.com", "phone": "9988776655", "annual_income": 960000, "requested_amount": 1500000, "employment_type": "Self-employed", "purpose": "Working capital for textile business expansion"},
        "crss": {"credit_score": 695, "existing_loans": 1, "default_history": "30 days", "dti_ratio": 45, "risk_category": "Medium"},
        "credit_approval": {"approved_amount": 1500000, "approval_conditions": "Hypothecation of inventory and book debts, personal guarantee of spouse, quarterly stock statements. Rate linked to external benchmark.", "officer_name": "Neha Gupta", "officer_id": "NG-2024-0387", "interest_rate": 10.50},
        "iris": {"account_number": "ICICI00098765432", "disbursement_amount": 1500000, "loan_tenure": 60, "interest_rate": 10.50, "booking_date": "2026-07-28", "status": "Booked"},
    },
    {
        "id": "USR-003", "name": "Arun Nair",
        "ai_recommendation": {"risk_category": "Low", "recommended_amount": 7500000, "confidence_score": 95, "reasoning": "Excellent credit profile with 820 score. IT business owner with 15+ years, strong EBITDA margins. Multiple existing loans managed well with zero defaults. DTI well within limits. High-value collateral available.", "model_version": "AI-CR-v3.3.0"},
        "human_override": {"override_reason": "Collateral available", "modified_amount": 8000000, "reviewer_name": "Suresh Iyer", "reviewer_notes": "Property being financed is pre-leased to a Fortune 500 tenant. Additional collateral of commercial space in prime location valued at 1.2Cr offered. LTV well within 75% threshold.", "exception_approved": "Yes"},
        "bdss": {"applicant_name": "Arun Nair", "email": "arun.nair@email.com", "phone": "9765432109", "annual_income": 3600000, "requested_amount": 8000000, "employment_type": "Business owner", "purpose": "Commercial property purchase for IT services office"},
        "crss": {"credit_score": 820, "existing_loans": 3, "default_history": "None", "dti_ratio": 28, "risk_category": "Low"},
        "credit_approval": {"approved_amount": 8000000, "approval_conditions": "Mortgage of proposed property, assignment of rental income, no-objection certificate from existing bankers. Disbursement directly to seller's account.", "officer_name": "Ananya Reddy", "officer_id": "AR-2024-0562", "interest_rate": 8.50},
        "iris": {"account_number": "AXIS00123456789", "disbursement_amount": 8000000, "loan_tenure": 180, "interest_rate": 8.50, "booking_date": "2026-09-01", "status": "Booked"},
    },
    {
        "id": "USR-004", "name": "Meera Joshi",
        "ai_recommendation": {"risk_category": "High", "recommended_amount": 250000, "confidence_score": 55, "reasoning": "Credit score of 620 is below threshold. Prior 60-day default recorded 8 months ago. DTI at 55% indicates significant existing debt burden. 4 active loans suggest over-leverage. Income of 6L is modest for additional debt. Recommend lower amount or declined.", "model_version": "AI-CR-v3.2.1"},
        "human_override": {"override_reason": "Manual override", "modified_amount": 400000, "reviewer_name": "Rohit Desai", "reviewer_notes": "Medical emergency case reviewed under humanitarian policy clause 14.3. Salary account with bank for 6 years. Employer is a government institution with stable income. Medical expense verification completed. Approved as exception case.", "exception_approved": "Yes"},
        "bdss": {"applicant_name": "Meera Joshi", "email": "meera.joshi@email.com", "phone": "9654321098", "annual_income": 600000, "requested_amount": 400000, "employment_type": "Salaried", "purpose": "Medical emergency funding for family health procedure"},
        "crss": {"credit_score": 620, "existing_loans": 4, "default_history": "60 days", "dti_ratio": 55, "risk_category": "High"},
        "credit_approval": {"approved_amount": 400000, "approval_conditions": "Medical expense receipts to be submitted within 30 days. Automatic deduction mandate. No further top-up loan for 12 months. Insurance coverage review recommended.", "officer_name": "Kavita Menon", "officer_id": "KM-2024-0293", "interest_rate": 13.00},
        "iris": {"account_number": "SBI00654321098", "disbursement_amount": 400000, "loan_tenure": 36, "interest_rate": 13.00, "booking_date": "2026-06-20", "status": "Booked"},
    },
    {
        "id": "USR-005", "name": "Vikram Singh Rathore",
        "ai_recommendation": {"risk_category": "Low", "recommended_amount": 22000000, "confidence_score": 88, "reasoning": "Strong credit profile with 790 score. Manufacturing business with 20+ year track record. Requested 2.5Cr against 6Cr+ annual income. Existing debt well managed. DTI moderate. Business expansion plan validated with projected 30% revenue increase. Slight reduction recommended for risk adjustment.", "model_version": "AI-CR-v3.3.0"},
        "human_override": {"override_reason": "Policy exception", "modified_amount": 25000000, "reviewer_name": "Deepak Agarwal", "reviewer_notes": "Existing borrowing relationship with 15 years. Plant and machinery valuation at 3.5Cr. Government MSME subsidy eligible. Approved under strategic corporate relationship program with board resolution.", "exception_approved": "Yes"},
        "bdss": {"applicant_name": "Vikram Singh Rathore", "email": "vikram.rathore@email.com", "phone": "9543210987", "annual_income": 7200000, "requested_amount": 25000000, "employment_type": "Business owner", "purpose": "Manufacturing plant expansion and new equipment purchase"},
        "crss": {"credit_score": 790, "existing_loans": 5, "default_history": "None", "dti_ratio": 35, "risk_category": "Low"},
        "credit_approval": {"approved_amount": 25000000, "approval_conditions": "Primary security: plant & machinery + factory land. Collateral: additional 2Cr property. DSA for MSME subsidy. Annual financial review. Capex verification within 6 months.", "officer_name": "Sanjay Kapoor", "officer_id": "SK-2024-0715", "interest_rate": 9.25},
        "iris": {"account_number": "BOB00876543210", "disbursement_amount": 25000000, "loan_tenure": 120, "interest_rate": 9.25, "booking_date": "2026-10-05", "status": "Booked"},
    },
    {
        "id": "USR-006", "name": "Priya Sharma",
        "ai_recommendation": {"risk_category": "Low", "recommended_amount": 1800000, "confidence_score": 85, "reasoning": "Good credit score of 740, clean repayment history. Single existing education loan being serviced regularly. DTI at 20% indicates strong repayment capacity. Co-applicant (father) is a government employee with stable income. Proposed amount slightly above recommended LTV.", "model_version": "AI-CR-v3.2.1"},
        "human_override": {"override_reason": "Collateral available", "modified_amount": 2000000, "reviewer_name": "Anand Tiwari", "reviewer_notes": "FD of 5L and LIC policy of 10L assigned as additional security. Co-applicant income of 15LPA considered. University is a top-50 global B-school. Placement records indicate strong ROI. Approved as education loan under priority sector.", "exception_approved": "Yes"},
        "bdss": {"applicant_name": "Priya Sharma", "email": "priya.sharma@email.com", "phone": "9321098765", "annual_income": 1200000, "requested_amount": 2000000, "employment_type": "Salaried", "purpose": "Higher education financing for MBA abroad"},
        "crss": {"credit_score": 740, "existing_loans": 1, "default_history": "None", "dti_ratio": 20, "risk_category": "Low"},
        "credit_approval": {"approved_amount": 2000000, "approval_conditions": "Disbursement in 2 installments (admission + tuition). Moratorium period of 24 months. Rate reduction of 0.5% upon maintaining 3.0+ GPA annually. Co-applicant guarantee mandatory.", "officer_name": "Ritu Agarwal", "officer_id": "RA-2024-0489", "interest_rate": 10.00},
        "iris": {"account_number": "YESB00432109876", "disbursement_amount": 2000000, "loan_tenure": 84, "interest_rate": 10.00, "booking_date": "2026-07-10", "status": "Booked"},
    },
    {
        "id": "USR-007", "name": "Abdul Khan",
        "ai_recommendation": {"risk_category": "Medium", "recommended_amount": 250000, "confidence_score": 65, "reasoning": "Credit score of 650 is average. One prior 30-day default 2 years ago. Single existing loan. DTI relatively healthy at 28%. Income of 4.2L sufficient for the proposed EMI. Vehicle financing has lower risk due to asset backing. Recommend 2.5L as prudent limit.", "model_version": "AI-CR-v3.2.1"},
        "human_override": {"override_reason": "Manual override", "modified_amount": 300000, "reviewer_name": "Farhan Qureshi", "reviewer_notes": "Applicant works with a reputed logistics firm with 7 years tenure. Salary account shows consistent credits for 4 years. Previous 30-day default was due to a technical delay (system migration issue). Approved as retail express loan.", "exception_approved": "Yes"},
        "bdss": {"applicant_name": "Abdul Khan", "email": "abdul.khan@email.com", "phone": "9876512345", "annual_income": 420000, "requested_amount": 300000, "employment_type": "Salaried", "purpose": "Two-wheeler purchase for daily commute to work"},
        "crss": {"credit_score": 650, "existing_loans": 1, "default_history": "30 days", "dti_ratio": 28, "risk_category": "Medium"},
        "credit_approval": {"approved_amount": 300000, "approval_conditions": "Hypothecation of vehicle, comprehensive insurance, no-prepayment penalty after 12 months. Auto-debit required. Post-dated cheques for 6 quarters.", "officer_name": "Mohit Chauhan", "officer_id": "MC-2024-0154", "interest_rate": 11.75},
        "iris": {"account_number": "PNB00321654987", "disbursement_amount": 300000, "loan_tenure": 48, "interest_rate": 11.75, "booking_date": "2026-08-20", "status": "Booked"},
    },
]

app = FastAPI(title="Credit Decisioning System")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")


@app.on_event("startup")
def startup():
    import threading
    from worker import run_loop
    t = threading.Thread(target=run_loop, daemon=True)
    t.start()


def list_submissions(service: str) -> List[dict]:
    dir_path = SERVICE_DIRS[service]
    results = []
    for fpath in sorted(dir_path.iterdir()):
        if fpath.suffix == ".json":
            try:
                data = json.loads(fpath.read_text(encoding="utf-8"))
                results.append(data)
            except json.JSONDecodeError:
                continue
    return results


def get_submission_file(service: str, application_id: str) -> Optional[Path]:
    dir_path = SERVICE_DIRS[service]
    for fpath in dir_path.iterdir():
        if fpath.suffix == ".json":
            try:
                data = json.loads(fpath.read_text(encoding="utf-8"))
                if data.get("application_id") == application_id:
                    return fpath
            except json.JSONDecodeError:
                continue
    return None


@app.get("/", response_class=HTMLResponse)
def index():
    return (BASE_DIR / "app" / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/api/applications")
def get_applications():
    return APPLICATIONS


@app.get("/api/services")
def get_services():
    return SERVICE_INFO


@app.get("/api/forms")
def get_forms():
    return SERVICE_FORMS


@app.get("/api/users")
def get_users():
    return USERS


@app.get("/api/submissions/{service}")
def get_submissions(service: str):
    if service not in SERVICE_DIRS:
        raise HTTPException(404, f"Unknown service: {service}")
    return list_submissions(service)


@app.get("/api/submissions/{service}/{application_id}")
def get_submission(service: str, application_id: str):
    if service not in SERVICE_DIRS:
        raise HTTPException(404, f"Unknown service: {service}")
    fpath = get_submission_file(service, application_id)
    if not fpath:
        raise HTTPException(404, f"No submission found for {application_id} in {service}")
    return json.loads(fpath.read_text(encoding="utf-8"))


@app.post("/api/submissions/{service}")
def create_submission(service: str, data: dict):
    if service not in SERVICE_DIRS:
        raise HTTPException(404, f"Unknown service: {service}")
    application_id = data.get("application_id")
    if not application_id:
        raise HTTPException(400, "application_id is required")
    submission_id = f"{service.upper()}-{uuid.uuid4().hex[:10].upper()}"
    record = {
        "submission_id": submission_id,
        "application_id": application_id,
        "service": service,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "data": {k: v for k, v in data.items() if k != "application_id"},
    }
    fpath = SERVICE_DIRS[service] / f"{submission_id}.json"
    fpath.write_text(json.dumps(record, indent=2), encoding="utf-8")

    tx_type = SERVICE_TX_MAP.get(service)
    if tx_type:
        _queue.enqueue(application_id, tx_type, record.get("data", {}))
    return record


@app.delete("/api/submissions/{service}/{application_id}")
def delete_submission(service: str, application_id: str):
    if service not in SERVICE_DIRS:
        raise HTTPException(404, f"Unknown service: {service}")
    fpath = get_submission_file(service, application_id)
    if not fpath:
        raise HTTPException(404, f"No submission found for {application_id} in {service}")
    fpath.unlink()
    return {"status": "deleted", "service": service, "application_id": application_id}


@app.delete("/api/applications/{application_id}")
def delete_application(application_id: str):
    deleted = []
    for service in SERVICE_DIRS:
        fpath = get_submission_file(service, application_id)
        if fpath:
            fpath.unlink()
            deleted.append({"service": service, "file": fpath.name})
    if not deleted:
        raise HTTPException(404, f"No submissions found for {application_id} in any service")
    return {"status": "deleted", "application_id": application_id, "removed": deleted}


@app.get("/api/queue/status")
def get_queue_status():
    pending = _queue.get_all_pending()
    apps: Dict[str, list] = {}
    for e in pending:
        apps.setdefault(e["application_id"], []).append({"tx_type": e["tx_type"], "status": e["status"], "service": e.get("service")})
    return {"total_pending": len(pending), "applications": apps}


@app.get("/api/applications/{application_id}/status")
def get_application_status(application_id: str):
    status_map = {}
    for service in SERVICE_DIRS:
        fpath = get_submission_file(service, application_id)
        submission = json.loads(fpath.read_text(encoding="utf-8")) if fpath else None
        status_map[service] = {
            "exists": submission is not None,
            "submission": submission,
        }
    return {"application_id": application_id, "services": status_map}


# ── Enterprise Audit Endpoints ──────────────────────────────────────────

EVIDENCE_VAULT_URL = os.getenv("EVIDENCE_VAULT_URL", "http://localhost:8001")
FABRIC_ADAPTER_URL = os.getenv("FABRIC_ADAPTER_URL", "http://localhost:8080")
BLOCK_INDEXER_APP = BASE_DIR / "07-block-indexer" / "app"
sys.path.insert(0, str(BLOCK_INDEXER_APP))

@app.get("/api/audit/applications")
def audit_list_applications():
    import httpx
    try:
        resp = httpx.get(f"{FABRIC_ADAPTER_URL}/audit/events", timeout=15)
        events = resp.json()
        apps = {}
        for e in events:
            aid = e.get("applicationId", "unknown")
            if aid not in apps:
                apps[aid] = {"applicationId": aid, "totalEvents": 0, "services": set(), "lastEvent": None}
            apps[aid]["totalEvents"] += 1
            apps[aid]["services"].add(e.get("service", ""))
            if not apps[aid]["lastEvent"] or e.get("timestamp", "") > apps[aid]["lastEvent"].get("timestamp", ""):
                apps[aid]["lastEvent"] = e
        return [{"applicationId": k, "totalEvents": v["totalEvents"], "services": list(v["services"]), "latestTimestamp": v["lastEvent"].get("timestamp", "") if v["lastEvent"] else ""} for k, v in apps.items()]
    except Exception as e:
        return {"error": str(e), "events": []}


@app.get("/api/audit/events/{event_key}/verify-evidence")
def verify_event_evidence(event_key: str, evidence_hash: str):
    import httpx
    try:
        resp = httpx.post(f"{EVIDENCE_VAULT_URL}/evidence/{event_key}/verify", json={"evidenceHash": evidence_hash}, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"eventKey": event_key, "verified": False, "error": str(e)}


@app.get("/api/audit/applications/{application_id}/replay")
def replay_application(application_id: str, mode: str = "full", timestamp: str = None):
    from replay_engine import AuditReplayEngine
    engine = AuditReplayEngine()
    if mode == "full":
        return engine.replay_complete_lifecycle(application_id)
    elif mode == "timestamp" and timestamp:
        return engine.replay_until_timestamp(application_id, timestamp)
    return engine.replay_complete_lifecycle(application_id)


@app.get("/api/health/services")
def services_health():
    import httpx
    results = {}
    services = {
        "fabric-adapter": "http://localhost:8080/health",
        "evidence-vault": "http://localhost:8001/health",
        "dashboard-api": "http://localhost:8002/health",
    }
    for name, url in services.items():
        try:
            resp = httpx.get(url, timeout=5)
            results[name] = {"status": "UP" if resp.status_code == 200 else "DEGRADED", "detail": resp.json()}
        except Exception as e:
            results[name] = {"status": "DOWN", "error": str(e)}
    return results

print("http://localhost:8000")
