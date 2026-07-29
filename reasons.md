# Design Decisions & Explanations

## Consensus & Ordering

| # | Question | Answer |
|---|----------|--------|
| 1 | **Why use RAFT ordering?** | RAFT provides deterministic transaction ordering without mining. It guarantees all peers receive blocks in the same sequence while supporting high availability. |

## Storage — CouchDB & Blockchain Files

| # | Question | Answer |
|---|----------|--------|
| 2 | **What is CouchDB?** | CouchDB is Hyperledger Fabric's World State database. It stores only the latest state of each key to support efficient chaincode queries. |
| 3 | **Where are blockchain blocks stored?** | Blocks are stored on each peer's filesystem under `/var/hyperledger/production/ledgerData`. They are not stored inside CouchDB. |

## Query Strategy — Fabric vs MongoDB

| # | Question | Answer |
|---|----------|--------|
| 4 | **Why not query Hyperledger Fabric directly?** | Fabric is optimized for immutable transactions, not analytical queries. MongoDB provides indexes and scalable querying for dashboards and reports. |

## Application Lifecycle Across Blocks

| # | Question | Answer |
|---|----------|--------|
| 5 | **Can one application span multiple blocks?** | Yes. Every workflow step creates a separate blockchain transaction. Those transactions are distributed across blocks based on commit timing. |
| 6 | **Example of one application across multiple blocks?** | APP-1001 may appear in Blocks 100, 101, 103, 107, 112, and 120. Each block contains transactions from many applications, not just one. |
| 7 | **What if the application lasts several weeks?** | The application simply continues generating transactions. New events are committed into whatever blocks are created at that time. |
| 8 | **Does Fabric append new transactions to the same block?** | No. Once a block is committed, it is permanently closed. Every new transaction goes into newly created blocks. |
| 9 | **How are blocks created?** | The Orderer collects transactions until `BatchTimeout` or `MaxMessageCount` is reached. It then creates a new immutable block. |
| 10 | **How do I visualize an application's lifecycle?** | Query all audit events by `applicationId` and display them as a timeline. The dashboard connects events across multiple blocks transparently. |

## Hashing & Integrity

| # | Question | Answer |
|---|----------|--------|
| 11 | **How is hashing used in blockchain?** | Every block stores the previous block's hash. This links blocks together so any modification invalidates all subsequent blocks. |
| 12 | **Can I implement my own previousHash?** | Yes. Create an application-level hash chain where every audit event stores the previous event's hash. This protects each application's lifecycle independently of the blockchain. |
| 13 | **Why don't I see previousHash in my ledger output?** | Fabric manages block hashes internally. Previous block hashes are not automatically included in transaction payloads unless explicitly retrieved through Fabric APIs. |
| 14 | **Can I expose block hashes?** | Yes. After a transaction commits, retrieve block metadata using Fabric APIs and export block hashes into MongoDB for reporting. |
| 15 | **When a block hash changes, how do I mine it?** | Hyperledger Fabric has no mining. A changed block hash indicates corruption or tampering, and recovery is done by restoring or synchronizing the ledger — not by mining a replacement block. |
| 16 | **Why use both an application hash chain and Fabric's block hash chain?** | Fabric secures the blockchain as a whole, while the application hash chain secures each application's sequence of audit events. Together they detect missing, reordered, or altered events. |

## Data Model — What Goes on Chain

| # | Question | Answer |
|---|----------|--------|
| 17 | **Should blockchain store the complete business JSON?** | No. Store only audit metadata, hashes, and changed fields. The complete JSON remains in the Evidence Vault. |
| 18 | **Can blockchain store every version?** | Yes. Every business change becomes a new immutable audit event. Together they reconstruct the complete application history. |
| 19 | **Can it record every transaction/row and retrieve it from World State?** | Yes. Each row or business event can be stored as a separate immutable transaction with a unique key. World State allows efficient retrieval while the Ledger permanently preserves every committed event. |
| 20 | **Why use unique keys for audit events?** | Unique keys prevent overwriting previous events. Every lifecycle step becomes an independent immutable audit record. |

## Recovery & Tampering

| # | Question | Answer |
|---|----------|--------|
| 21 | **How do I recover if someone tampers with CouchDB?** | Stop the peer, delete the corrupted World State, restart the peer, and replay the immutable blockchain ledger. Fabric automatically rebuilds CouchDB from the committed blocks. |
| 22 | **Can someone tamper with the blockchain ledger?** | Any modification changes block hashes and breaks the chain. In production, peers detect inconsistencies and recover from healthy peers. |
| 23 | **What happens if MongoDB is corrupted?** | MongoDB is only a read model. Replay committed blockchain transactions through the Export Service to rebuild every collection. |

## Monitoring & Observability

| # | Question | Answer |
|---|----------|--------|
| 24 | **How do I know if my ledger is healthy?** | Monitor ledger height, peer synchronization, RAFT leader status, block validation, and integrity verification. These metrics should be exposed in an observability dashboard. |
| 25 | **Can I reconstruct an application years later?** | Yes. Query all audit events by `applicationId` to rebuild the complete application lifecycle regardless of when the events occurred. |
