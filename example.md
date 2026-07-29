# Example: Application APP-1001

Suppose a customer submits a loan application.

- **Application ID**: APP-1001
- **Customer**: Rajesh Kumar

The application moves through your workflow:

```
BDSS (Business Decision Support)
  → CRSS (Credit Risk Scoring)
  → AI Recommendation
  → Human Override
  → Credit Approval
  → IRIS Booking
```

Every completed stage generates one audit event with an application-level SHA-256 hash chain.

---

## Where historical data is stored

Hyperledger Fabric stores data in two places: the **blockchain** (immutable history) and the **world state** (current state).

```
                          HYPERLEDGER FABRIC STORAGE
  ┌─────────────────────────────────────────────────────────────────────────┐
  │                                                                         │
  │  PEER FILESYSTEM                          COUCHDB                       │
  │  ┌─────────────────────┐                  ┌──────────────────────┐      │
  │  │   BLOCKCHAIN        │                  │   WORLD STATE        │      │
  │  │                     │                  │                      │      │
  │  │ Block #100          │                  │ Key → Latest Value   │      │
  │  │ Block #101          │                  │                      │      │
  │  │ Block #102          │                  │ APP-1001-TX006 = {   │      │
  │  │ Block #103          │                  │   ... latest only }  │      │
  │  │ ...                 │                  │                      │      │
  │  │ Block #120          │                  │ (only 1 doc per key) │      │
  │  │                     │                  │                      │      │
  │  │ (all blocks ever)   │                  │ (current state only) │      │
  │  └─────────────────────┘                  └──────────────────────┘      │
  │                                                                         │
  │           ↑ Each block stores full tx data ↑                            │
  │           ↑ CouchDB stores only the latest value per key ↑              │
  └─────────────────────────────────────────────────────────────────────────┘
```

### 1. Blockchain (peer filesystem) — full history

Every block is an append-only block file on each peer's disk.

```
/var/hyperledger/production/ledgerData/chains/auditchannel/
└── blockfile_000000    ← contains Block #0, #1, #2, ... #100, #101, etc.
```

Each block stores:
- **Header**: block number, hash of previous block, data hash
- **Data**: all transactions in that block (full content)
- **Metadata**: validation codes, commit hash

This means **every historical value** is preserved. You can replay all blocks to rebuild the world state from scratch.

### 2. World state (CouchDB) — current values only

CouchDB stores the latest state for each key — not history.

```
Database:  auditchannel_ (channel name + underscore)
Documents: one per unique key (latest value only)

AUDIT-{auditId}-{txId}  →  {service:"bdss",             businessEvent:"TX_TX001", ...}
AUDIT-{auditId}-{txId}  →  {service:"crss",             businessEvent:"TX_TX002", ...}
AUDIT-{auditId}-{txId}  →  {service:"ai_recommendation",businessEvent:"TX_TX003", ...}
AUDIT-{auditId}-{txId}  →  {service:"human_override",   businessEvent:"TX_TX004", ...}
AUDIT-{auditId}-{txId}  →  {service:"credit_approval",  businessEvent:"TX_TX005", ...}
AUDIT-{auditId}-{txId}  →  {service:"iris",             businessEvent:"TX_TX006", ...}
```

The event key is formed as `AUDIT-{auditId}-{transactionId}` (see `06-chaincode/audit-contract/lib/auditContract.js:16`). Since each key is unique, no key is ever overwritten. Every event stays in CouchDB permanently.

### 3. The block chain (how blocks link)

```
Block #99                    Block #100                   Block #101
┌──────────────────┐         ┌──────────────────┐         ┌──────────────────┐
│ Header           │         │ Header           │         │ Header           │
│  Number: 99      │         │  Number: 100     │         │  Number: 101     │
│  PrevHash: ...   │ ──────→ │  PrevHash: H(99) │ ──────→ │  PrevHash: H(100)│
│  DataHash: ...   │         │  DataHash: ...   │         │  DataHash: ...   │
├──────────────────┤         ├──────────────────┤         ├──────────────────┤
│ Data (txs)       │         │ Data (txs)       │         │ Data (txs)       │
│ ...              │         │ APP-1001: BDSS   │         │ APP-1001: CRSS   │
│                  │         │ APP-1002: BDSS   │         │ APP-1005: BDSS   │
│                  │         │ APP-1003: BDSS   │         │                  │
└──────────────────┘         └──────────────────┘         └──────────────────┘
```

Each block's header contains `PreviousHash = SHA256(previous block header)`. This chains blocks together. Tampering with any block would change its hash and break the link to the next block — detectable by every peer.

### 4. Application-level hash chain

Beyond Fabric's block-level chain, each audit event includes its own SHA-256 hash that chains to the previous event for the same application:

```
currentHash = SHA256(
    applicationId | businessEvent | timestamp | evidenceHash |
    previousHash | correlationId | changedFields | sequence
)
```

This is computed by the **Transaction Orchestrator** (`02-transaction-orchestrator/app/orchestrator.py:154`) before submission, using `sort_keys=True, separators=(',', ':')` to match CouchDB's alphabetical key ordering. The chaincode also recomputes the hash independently in `VerifyAuditHashChain()` (`06-chaincode/audit-contract/lib/auditContract.js:148`).

### 5. Rebuilding history

CouchDB gives you current state. For historical versions of a key, query the blockchain via chaincode:

```
GetApplicationAuditHistory("APP-1001")
     │
     ▼
ctx.stub.getQueryResult({selector: {applicationId: "APP-1001"}})
     │
     ▼
Returns: [{...event with full field history}, ...]
```

The chaincode function `GetApplicationAuditHistory` (`06-chaincode/audit-contract/lib/auditContract.js:45`) uses CouchDB's rich query to return all events for an application, sorted by sequence number. This is the recommended way to retrieve audit history — not `getHistoryForKey()`, which returns Fabric-level versioning rather than application-level events.

### 6. Summary

| What | Where | Stores | Accessed by |
|------|-------|--------|-------------|
| Full block history | Peer filesystem (`blockfile_*`) | Every transaction ever committed | `peer node rebuild-dbs`, block events |
| Key history index | Peer filesystem (LevelDB) | Every version of every key | `getHistoryForKey()` |
| Current world state | CouchDB (`auditchannel_`) | Latest value per key | `getState()`, `getQueryResult()` |
| Application hash chain | Event `currentHash` field | Links events per application | `VerifyAuditHashChain()` (`auditContract.js:148`) |
| Audit read model | MongoDB (`audit_ledger`) | Query-optimized replica | Dashboard API (`08-Dashboard/app/main.py`) |

---

## Application blocks on the chain

```
Block #100              Block #101              Block #103              Block #107
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│ APP-1001 BDSS    │    │ APP-1001 CRSS    │    │ APP-1001 AI_REC │    │ APP-1001 HUMAN   │
│ APP-1002 BDSS    │    │ APP-1005 BDSS    │    │ APP-1007 BDSS   │    └──────────────────┘
│ APP-1003 BDSS    │    └──────────────────┘    │ APP-1008 CRSS   │
└──────────────────┘                            └──────────────────┘

Block #112              Block #120
┌──────────────────┐    ┌──────────────────┐
│ APP-1001 CREDIT  │    │ APP-1001 IRIS    │
└──────────────────┘    └──────────────────┘
```

APP-1001 spans 6 blocks (100, 101, 103, 107, 112, 120). Other apps' transactions fill the gaps — normal on a shared channel.

---

## Query result

| Block | TxID   | Step  | businessEvent       | Service            | Source submission file                          |
|-------|--------|-------|---------------------|--------------------|------------------------------------------------|
| 100   | A1B2C3 | TX001 | TX_TX001            | bdss               | `01-business-services/01-bdss/submissions/BDSS-{uuid}.json` |
| 101   | D4E5F6 | TX002 | TX_TX002            | crss               | `01-business-services/02-crss/submissions/CRSS-{uuid}.json` |
| 103   | G7H8I9 | TX003 | TX_TX003            | ai_recommendation  | `01-business-services/03-ai-recommendation-engine/submissions/AI_RECOMMENDATION-{uuid}.json` |
| 107   | J1K2L3 | TX004 | TX_TX004            | human_override     | `01-business-services/04-human-override/submissions/HUMAN_OVERRIDE-{uuid}.json` |
| 112   | M4N5O6 | TX005 | TX_TX005            | credit_approval    | `01-business-services/05-credit-approval/submissions/CREDIT_APPROVAL-{uuid}.json` |
| 120   | P7Q8R9 | TX006 | TX_TX006            | iris               | `01-business-services/06-iris/submissions/IRIS-{uuid}.json` |
