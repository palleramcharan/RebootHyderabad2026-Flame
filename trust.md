# Trust Model — Enterprise Immutable Audit Ledger

## Why This Platform Is Trustworthy

### Immutability
- **Append-only blockchain**: Once a block is committed by RAFT consensus, it is permanently sealed. No transaction can be modified, deleted, or reordered.
- **Block hash chain**: Every block stores `previousHash = SHA256(previous block header)`. Tampering with any block changes its hash and breaks every subsequent block — immediately detectable by all peers.
- **Application-level hash chain**: Each audit event stores `currentHash = SHA256(applicationId | businessEvent | timestamp | evidenceHash | previousHash | correlationId | changedFields | sequence)`. Events for the same application form an independent chain, protecting against missing, reordered, or altered events within an application lifecycle.

### No Single Point of Failure
- **RAFT consensus**: Transaction ordering is agreed by a cluster, not a single node. All peers receive identical blocks in identical sequence.
- **CouchDB can be rebuilt**: If CouchDB (world state) is corrupted, delete it and replay the immutable blockchain. Fabric automatically reconstructs the entire world state from committed blocks.
- **MongoDB is disposable**: MongoDB is a read-only cache built from Fabric events. If corrupted, replay the Export Service to rebuild every collection from scratch.

### Evidence Integrity
- **SHA-256 evidence hashing**: Every business JSON submitted to the Evidence Vault is SHA-256 hashed. The hash is stored on the blockchain, while the original JSON stays in the Evidence Vault.
- **Verification API**: The chaincode function `VerifyEvidence()` compares a provided hash against the stored `evidenceHash` on the blockchain. The Dashboard API also provides independent hash verification.
- **No PII on blockchain**: Only audit metadata, evidence hashes, and changed fields are stored on-chain. Full business JSON remains in the Evidence Vault — minimizing regulatory exposure.

### Data Lineage
- **Field change tracking**: The Transaction Orchestrator automatically diffs the previous payload against the current payload before submission. Only changed fields are recorded on-chain, providing a complete audit trail of what changed at each step.
- **Correlation tracking**: Every event in a multi-step workflow shares a `correlationId`, linking all steps of a single application lifecycle.

---

## Key Features

| Feature | How It Works |
|---------|-------------|
| Immutable Audit Trail | Every business event is a separate blockchain transaction with a unique key. No event can be overwritten or deleted. |
| Dual Hash Chains | Fabric's block-level chain protects the ledger structure. The application-level chain protects each application's event sequence independently. |
| RAFT Consensus | Deterministic, crash-fault-tolerant ordering. No mining, no forks — all peers agree on block order. |
| CouchDB World State | Rich queryable state database for chaincode execution. Supports JSON queries, indexes, and pagination. |
| MongoDB Read Model | Query-optimized replica for dashboards, search, and analytics. Never the source of truth — always rebuildable from Fabric. |
| Evidence Vault | Original business JSON stored separately with SHA-256 integrity verification. Not on the blockchain — reducing chain bloat. |
| Audit Replay Engine | Reconstruct complete application state at any point in time by replaying all audit events for a given `applicationId`. |
| Integrity Monitor | Continuously verifies the application hash chain and evidence hashes. Detects missing, reordered, or tampered events. |
| Field Change Detection | Automatic diff between previous and current payload. Only changed fields are recorded — not full payloads. |
| Lifecycle Validation | Enforces correct workflow transition order (BDSS → CRSS → AI Recommendation → Human Override → Credit Approval → IRIS Booking). Invalid transitions are rejected. |
| Transaction Queue | Durable queue with retry logic. Failed submissions are persisted and can be retried without data loss. |
| 10-Panel Dashboard | Overview, Application Timeline, Audit Explorer, Blockchain Explorer, Field Changes, Evidence Verification, Integrity, Replay Engine, Health. |

---

## Security & Recovery

| Scenario | Recovery |
|----------|----------|
| CouchDB tampered/corrupted | Stop peer → delete CouchDB data → restart peer → Fabric replays blockchain to rebuild world state automatically. |
| Blockchain file tampered | Modified block hash breaks chain. Peer detects inconsistency on next block validation. Recover from a healthy peer replica. |
| MongoDB corrupted | MongoDB is a read model. Re-run the Export Service (`--rebuild`) to re-index all events from Fabric. No data loss. |
| Evidence Vault lost | Evidence hashes are on-chain. Re-submit original business payloads to regenerate evidence hashes and verify against chain. |
| Peer failure | RAFT handles single-peer failures. Other peers continue servicing requests. Replace and synchronize the failed peer from the cluster. |

---

## Design Principles

1. **No PII on blockchain** — only audit metadata, evidence hashes, and changed fields
2. **Separation of concerns** — blockchain for immutability, CouchDB for chaincode queries, MongoDB for analytics, Evidence Vault for original JSON
3. **Defense in depth** — dual hash chains (block-level + application-level) protect against different attack vectors
4. **Recoverability** — every component except the blockchain itself is disposable and rebuildable from the chain
5. **Deterministic ordering** — RAFT guarantees all peers see identical block sequences; no forks, no reorganization
6. **Minimal on-chain data** — only what is needed for audit integrity; bulk data stays in application services
