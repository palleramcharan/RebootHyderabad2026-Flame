# Enterprise Audit Ledger

## What Does This System Do?

Imagine you run a bank. A customer applies for a loan. That application needs to go through several departments — first credit check, then risk scoring, then manager approval, then final booking. Each department reviews and changes the application. This system **records every single change** on a blockchain so nobody can tamper with the history later.

**Think of it like a black box in an airplane** — it records every event in order, and once recorded, nobody can change or delete it.

---

## End-to-End Architecture

Below is the complete flow from business data to blockchain, with every component explained.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ 01-business-services/  —  The Business Applications                      │
│                                                                          │
│   Each folder = one department in the loan lifecycle:                    │
│    01-bdss/           →  Business Decision Support (initial review)      │
│    02-crss/           →  Credit Risk Scoring (risk calculation)          │
│    03-ai-recommendation/ → AI Recommendation Engine (AI suggests)        │
│    04-human-override/ →  Human Override (manager reviews AI)            │
│    05-credit-approval/ → Credit Approval (final decision)               │
│    06-iris/           →  IRIS Booking (loan gets booked)                │
│                                                                          │
│   Inside each: submissions/*.json                                        │
│   These are SAMPLE loan applications with fields like:                   │
│     applicant_name, requested_amount, employment_type, etc.              │
│   Each department's file represents what that department sees/changes.   │
└──────────────────────┬───────────────────────────────────────────────────┘
                       │
                       │  1. Read submission JSON files
                       ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ scripts/enqueue_submissions.py  —  The Queue Loader                      │
│                                                                          │
│   Reads all submission files and creates QUEUE TICKETS.                  │
│   Each ticket = one application + one department combination.            │
│                                                                          │
│   Example output:                                                        │
│     "APP-1001 needs BDSS (TX001)"                                        │
│     "APP-1001 needs CRSS (TX002)"                                        │
│     "APP-1001 needs AI (TX003)"                                          │
│     ... (6 tickets per application)                                      │
│                                                                          │
│   Also maps: BDSS → TX001, CRSS → TX002, ..., IRIS → TX006              │
└──────────────────────┬───────────────────────────────────────────────────┘
                       │
                       │  2. Write tickets as JSON files
                       ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ 02-transaction-orchestrator/queue/ordered_proposals/  —  The Queue      │
│                                                                          │
│   A simple file-based queue. Each ticket is a .json file named:          │
│     {seq}_{tx_type}_{queue_id}.json                                      │
│                                                                          │
│   Example files:                                                         │
│     0001_TX001_abc123.json  →  "APP-1001 at BDSS, status=queued"         │
│     0002_TX002_def456.json  →  "APP-1001 at CRSS, status=queued"         │
│                                                                          │
│   Ticket statuses: queued → processing → completed / failed              │
│   Files are organized by application_id subfolder (APP-1001/, APP-1002/) │
└──────────────────────┬───────────────────────────────────────────────────┘
                       │
                       │  3. Pick up next pending ticket
                       ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ 02-transaction-orchestrator/app/  —  The Orchestrator Engine            │
│                                                                          │
│  worker.py  (The Foreman)                                                │
│   ├─ Runs in batches (--once flag = process one batch and stop)         │
│   ├─ Asks the queue "what's pending?"                                   │
│   └─ Hands each ticket to the orchestrator                              │
│                                                                          │
│  orchestrator.py  (The Quality Inspector)                                │
│   ├─ Step A: lifecycle_manager.py validates the ORDER                    │
│   │   (e.g. "Can't run Credit Approval before Risk Scoring")            │
│   │   └─ Tracks progress in state/{app_id}.json files                   │
│   ├─ Step B: Looks up previous record's hash from blockchain             │
│   │   (via GET http://localhost:8080/audit/applications/{app}/events)   │
│   ├─ Step C: evidence_client.py stores a fingerprint of the data        │
│   │   └─ If evidence vault (port 8001) is down, computes locally        │
│   ├─ Step D: Builds the audit event with all fields + hashes            │
│   ├─ Step E: Submits to blockchain via Fabric adapter                   │
│   └─ Step F: On success → advance lifecycle, mark ticket completed      │
│                     On failure → mark ticket failed                     │
│                                                                          │
│  transaction_queue.py  (The Ticketing System)                            │
│   ├─ enqueue()  → Create a new ticket                                   │
│   ├─ dequeue()  → Pick next queued ticket and mark it "processing"      │
│   ├─ complete() → Mark ticket done                                      │
│   └─ fail()     → Mark ticket failed with reason                        │
│                                                                          │
│  lifecycle_manager.py  (The Rule Book)                                   │
│   └─ Tells you: what step comes next, what's allowed, what's not        │
└──────────────────────┬───────────────────────────────────────────────────┘
                       │
                       │  4. POST audit event as JSON (HTTP)
                       ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ 04-fabric-adapter/  —  The Blockchain Translator                         │
│                                                                          │
│   Written in Node.js. Acts as a BRIDGE between Python and Hyperledger.   │
│                                                                          │
│  src/server.js  (Express.js web server on port 8080)                     │
│   ├─ GET  /health                          → "Is the adapter alive?"     │
│   ├─ POST /audit/events                    → Submit a new audit event   │
│   ├─ GET  /audit/events                    → Get ALL events             │
│   ├─ GET  /audit/events/{eventKey}         → Get one event by its key   │
│   ├─ GET  /audit/applications/{app}/events → Get events for one app     │
│   └─ ... (more query endpoints)                                          │
│                                                                          │
│  src/fabric-connector.js  (Fabric Gateway Client)                        │
│   ├─ connect()    → Opens a gRPC connection to the Fabric peer          │
│   ├─ submit()     → Calls chaincode function to WRITE data              │
│   ├─ evaluate()   → Calls chaincode function to READ data               │
│   └─ isNetworkReady() → Health check that also refreshes connection     │
│                                                                          │
│  src/config.js    (reads crypto certs, channel name, chaincode name)     │
│                                                                          │
│  Flow:                                                                    │
│   HTTP request arrives → ensureConnected middleware (refresh if needed)  │
│   → route handler calls fabric.CreateAuditEvent(json)                    │
│   → fabric-connector calls submitTransaction on chaincode                │
│   → chaincode validates and stores → response flows back                │
└──────────────────────┬───────────────────────────────────────────────────┘
                       │
                       │  5. Chaincode call (gRPC)
                       ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ 05-fabric-network/  —  The Blockchain Network (Hyperledger Fabric)      │
│                                                                          │
│  This is the IMMUTABLE VAULT. Once data is written here, it can't be    │
│  changed or deleted. Anyone can verify the history.                      │
│                                                                          │
│  Components running in Docker:                                           │
│                                                                          │
│  peer0.org1.example.com (port 7051)                                      │
│   ├─ The actual blockchain node that stores the ledger                   │
│   ├─ Runs the chaincode in a separate container                          │
│   └─ Connected to CouchDB (port 5984) for world state                    │
│                                                                          │
│  orderer0.example.com (port 7050, 9443)                                  │
│   ├─ RAFT consensus node                                                 │
│   ├─ Receives transactions, orders them, creates blocks                  │
│   └─ No system channel — uses Channel Participation API                 │
│                                                                          │
│  ca-org1 (port 7054)                                                     │
│   └─ Certificate Authority — issues identities for everything            │
│                                                                          │
│  cli                                                                     │
│   └─ Command-line tool for manual Fabric operations                     │
│                                                                          │
│  Chaincode: audit-contract (auditEvent.js)                               │
│   ├─ CreateAuditEvent() → Validates all fields, stores event in world   │
│   │   state with hash chain linking                                     │
│   ├─ GetAllAuditEvents() → Returns every stored event                   │
│   ├─ GetApplicationAuditHistory() → All events for one application      │
│   ├─ VerifyAuditHashChain() → Checks integrity of the hash chain        │
│   └─ GetFieldChangeHistory() → What changed across all steps            │
│                                                                          │
│  docker-compose.yaml defines all these services.                         │
│  02-execute_fabric.ps1 builds, starts, creates channel, deploys code.   │
└──────────────────────┬───────────────────────────────────────────────────┘
                       │
                       │  6. HTTP query (read events)
                       ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ 08-Dashboard/  —  The Visual Dashboard (Optional)                        │
│                                                                          │
│  generate_report.py                                                      │
│   ├─ Fetches events live from Fabric adapter at localhost:8080          │
│   └─ Generates a standalone HTML file: dashboard.html                   │
│                                                                          │
│  dashboard.html                                                          │
│   ├─ Shows metrics (blocks, transactions, TPS)                          │
│   ├─ Application progress grid with step dots                           │
│   ├─ Blockchain timeline view                                           │
│   └─ Filter by application                                              │
│                                                                          │
│  Run: .\execute\05-execute_dash.ps1                                     │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Step-by-Step: How It Works (Simple)

### 1. The Application Data

Inside `01-business-services/`, each department folder has sample application JSON files (like `applicant_name`, `requested_amount`, etc.). These are the inputs — they represent what each department sees or changes about a loan application.

### 2. The Queue (Think of a Ticket Counter)

`scripts/enqueue_submissions.py` reads all those application files and creates **tickets** in a queue. Each ticket says: "APP-1001 needs to go through Department 1 (BDSS), then Department 2 (CRSS), then Department 3..." — one ticket per department per application.

The tickets are stored as simple `.json` files in `02-transaction-orchestrator/queue/ordered_proposals/`.

### 3. The Orchestrator (The Foreman)

`worker.py` acts like a foreman on a factory line. It checks the queue, picks up pending tickets one by one, and processes them in strict order:

- **Step 1: Validate** — Makes sure Department 2 doesn't try to run before Department 1.
- **Step 2: Compute a fingerprint (hash)** — Takes data like "who changed what" and runs it through a formula that produces a unique code. If even one comma changes, the code changes completely.
- **Step 3: Chain it** — Each new record stores the previous record's unique code. This creates a **chain**: if someone tries to change record #3, record #4's stored code won't match anymore.
- **Step 4: Submit to Blockchain** — Sends the record to be permanently stored.

### 4. The Blockchain (The Vault)

Hyperledger Fabric acts as the secure vault. Once a record goes in:

- **Nobody can alter it** (immutable)
- **Everyone can read it** (transparent)
- **The chain of fingerprints proves nothing was tampered with**

The Fabric Adapter (`04-fabric-adapter/`) is like a **translator** — it takes HTTP requests from the orchestrator and converts them into blockchain commands that Fabric understands.

### 5. Viewing the Records

After processing, you can see all records by visiting:
- `http://localhost:8080/audit/events` — shows all events
- `http://localhost:8080/audit/applications/APP-1001/events` — shows events for one application

Or generate a visual dashboard by running:
```
.\execute\05-execute_dash.ps1
```
This opens `08-Dashboard/dashboard.html` in your browser with charts and timelines.

---

## What Goes Into the Blockchain?

The system records **audit metadata**, NOT personal information:

| Field | Meaning | Example |
|-------|---------|---------|
| applicationId | Which loan application | APP-1001 |
| businessEvent | What department processed it | TX_BDSS |
| userId | Who did it | SYSTEM |
| timestamp | When | 2026-07-28T10:30:00Z |
| correlationId | Links related events together | (UUID) |
| previousHash | Code of the previous event | (64-char hex) |
| currentHash | This event's unique code | (64-char hex) |
| evidenceHash | Fingerprint of the actual business data | (64-char hex) |
| changedFields | What data changed from previous step | ["requested_amount"] |

**Personal data stays in the business application database.** The blockchain only stores fingerprints (hashes) of that data. This is like recording "the contract was signed" on a public ledger without putting the contract text there.

---

## The 6 Department Lifecycle

| # | Short Name | Full Name | What Happens |
|---|-----------|-----------|--------------|
| 1 | BDSS | Business Decision Support | Initial application review |
| 2 | CRSS | Credit Risk Scoring | Calculate risk score |
| 3 | AI | AI Recommendation | AI suggests approve/decline |
| 4 | Human Override | Human Override | Manager reviews AI suggestion |
| 5 | Credit Approval | Credit Approval | Final approval decision |
| 6 | IRIS | IRIS Booking | Loan gets booked in system |

Transactions **must** flow in this order. You can't get credit approval before risk scoring.

---

## Services That Are Running

| Service | What It Is | Port |
|---------|-----------|------|
| Fabric Adapter | Translator between Python and blockchain | 8080 |
| Peer | The node that stores blockchain data | 7051 |
| Orderer | Orders transactions into blocks | 7050 |
| CouchDB | Internal database for the blockchain peer | 5984 |
| CA | Certificate authority (issues IDs) | 7054 |
| MongoDB | General-purpose database | 27017 |

---

## How to Run the Whole Flow

```powershell
# 1. Install tools
.\execute\01-execute_setup.ps1

# 2. Start blockchain, load queue, process everything
.\execute\02-execute_fabric.ps1

# 3. Generate the visual dashboard
.\execute\05-execute_dash.ps1
```

### If You Want to Do It Step by Step

```bash
# Load applications into the queue
python scripts/enqueue_submissions.py

# Process one batch (each batch handles 1 step per application)
python 02-transaction-orchestrator/app/worker.py --once
# Run again until it says processed=0
python 02-transaction-orchestrator/app/worker.py --once

# See the records
curl http://localhost:8080/audit/events
```

---

## Key Ideas to Remember

| Idea | Simple Explanation |
|------|-------------------|
| **Immutable** | Once written, it never changes. Like carving in stone. |
| **Hash Chain** | Each record locks onto the previous one. Breaking one link breaks everything after it. |
| **Lifecycle** | Steps 1 → 2 → 3 → 4 → 5 → 6. No skipping, no reordering. |
| **No PII on chain** | Only fingerprints of data, not the data itself. |
| **Evidence Fallback** | If the evidence vault is down, the system computes the fingerprint locally. |
