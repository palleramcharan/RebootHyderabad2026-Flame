$PASS = 0
$FAIL = 0

function Test-Pass($name) { $script:PASS += 1; Write-Host "  PASS: $name" }
function Test-Fail($name) { $script:FAIL += 1; Write-Host "  FAIL: $name" }

Write-Host "============================================"
Write-Host "  Local Tests (no Docker / Fabric required)"
Write-Host "============================================"

# 1. Evidence Vault — SHA-256 hash generation
Write-Host ""
Write-Host "--- 1. Evidence Vault: hash_generator ---"
$result = .\.venv\Scripts\python -c @'
import sys, tempfile, os
sys.path.insert(0, '03-evidence-vault')
from event_builder.hash_generator import hash_string, hash_file, hash_bytes

h1 = hash_string('hello')
h2 = hash_string('hello')
h3 = hash_string('world')
assert h1 == h2, 'same input should produce same hash'
assert h1 != h3, 'different input should produce different hash'
assert len(h1) == 64, 'SHA-256 should be 64 hex chars'

with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
    f.write('test data')
    f.flush()
    f.close()
    h4 = hash_file(f.name)
    os.unlink(f.name)
assert len(h4) == 64, 'file hash should be 64 hex chars'

h5 = hash_bytes(b'test data')
assert h5 == h4, 'file and bytes should produce same hash'
print('hash_generator: all assertions passed')
'@ 2>&1
Write-Host "$result"
if ($LASTEXITCODE -eq 0) { Test-Pass "hash_generator" } else { Test-Fail "hash_generator" }

# 2. Evidence Vault — audit event builder
Write-Host ""
Write-Host "--- 2. Evidence Vault: evidence_event ---"
$result = .\.venv\Scripts\python -c @'
import sys, json
sys.path.insert(0, '03-evidence-vault')
from event_builder.evidence_event import build_audit_event

event = build_audit_event(
    submission_id='TEST-001',
    application_id='APP-TEST',
    service='test-service',
    sha256_hash='abc123',
    event_type='TEST_EVENT',
    user_id='tester',
    correlation_id='corr-test-001',
    metadata={'key': 'value'}
)
assert event['submissionId'] == 'TEST-001', 'submissionId mismatch'
assert event['applicationId'] == 'APP-TEST', 'applicationId mismatch'
assert event['service'] == 'test-service', 'service mismatch'
assert event['sha256Hash'] == 'abc123', 'sha256Hash mismatch'
assert event['eventType'] == 'TEST_EVENT', 'eventType mismatch'
assert event['userId'] == 'tester', 'userId mismatch'
assert event['correlationId'] == 'corr-test-001', 'correlationId mismatch'
assert event['metadata']['key'] == 'value', 'metadata mismatch'
assert event['operation'] == 'CREATE', 'operation should default to CREATE'
assert event['channelName'] == 'auditchannel', 'channelName should default to auditchannel'
assert event['mspId'] == 'Org1MSP', 'mspId should default to Org1MSP'
print('evidence_event: all assertions passed')
'@ 2>&1
Write-Host "$result"
if ($LASTEXITCODE -eq 0) { Test-Pass "evidence_event" } else { Test-Fail "evidence_event" }

# 3. Transaction Queue — enqueue/dequeue/complete/fail
Write-Host ""
Write-Host "--- 3. Transaction Orchestrator: transaction_queue ---"
$result = .\.venv\Scripts\python -c @'
import sys, os, tempfile, shutil
sys.path.insert(0, '02-transaction-orchestrator/app')

os.environ['QUEUE_BASE'] = tempfile.mkdtemp()
import transaction_queue as tq
tq.QUEUE_DIR = tq.BASE_DIR / 'queue' / 'ordered_proposals'
# Use a temp dir to avoid leftover state from prior runs
_orig_queue_dir = tq.QUEUE_DIR
tq.QUEUE_DIR = tq.BASE_DIR.parent / tempfile.mkdtemp()
tq.QUEUE_DIR.mkdir(parents=True, exist_ok=True)
from transaction_queue import TransactionQueue

q = TransactionQueue()

entry = q.enqueue('TEST-APP', 'TX001', {'test': True})
assert entry['application_id'] == 'TEST-APP'
assert entry['tx_type'] == 'TX001'
assert entry['status'] == 'queued'
assert entry['service'] == 'bdss'

dequeued = q.dequeue('TEST-APP')
assert dequeued is not None, 'dequeue should return entry'
assert dequeued['status'] == 'processing'

completed = q.complete('TEST-APP', entry['queue_id'])
assert completed, 'complete should succeed'

entry2 = q.enqueue('TEST-APP', 'TX002', {'step': 2})
dequeued2 = q.dequeue('TEST-APP')
failed = q.fail('TEST-APP', entry2['queue_id'], 'test failure')
assert failed, 'fail should succeed'

pending = q.get_all_pending()
assert len(pending) == 0, 'no pending items after complete/fail'

total = q.get_queue('TEST-APP')
assert len(total) == 2, 'should have 2 total entries'

shutil.rmtree(os.environ['QUEUE_BASE'])
print('transaction_queue: all assertions passed')
'@ 2>&1
Write-Host "$result"
if ($LASTEXITCODE -eq 0) { Test-Pass "transaction_queue" } else { Test-Fail "transaction_queue" }

# 4. Lifecycle Manager — state transitions
Write-Host ""
Write-Host "--- 4. Transaction Orchestrator: lifecycle_manager ---"
$result = .\.venv\Scripts\python -c @'
import sys, os, tempfile
sys.path.insert(0, '02-transaction-orchestrator/app')

os.environ['STATE_BASE'] = tempfile.mkdtemp()
import lifecycle_manager as lm_mod
lm_mod.STATE_DIR = lm_mod.BASE_DIR.parent / tempfile.mkdtemp()
lm_mod.STATE_DIR.mkdir(parents=True, exist_ok=True)
from lifecycle_manager import LifecycleManager, TX_TO_SERVICE, LIFECYCLE

lm = LifecycleManager()

step = lm.get_current_step('APP-NEW')
assert step is None, 'new app should have no current step'

valid = lm.validate_transition('APP-NEW', 'bdss')
assert valid['valid'], 'first transition to bdss should be valid'

lm.advance('APP-NEW', 'bdss')
step = lm.get_current_step('APP-NEW')
assert step == 'bdss', 'current step should be bdss after advance'

valid = lm.validate_transition('APP-NEW', 'crss')
assert valid['valid'], 'bdss -> crss should be valid'

valid = lm.validate_transition('APP-NEW', 'bdss')
assert not valid['valid'], 'bdss -> bdss should be invalid (already completed)'

for svc in ['crss', 'ai_recommendation', 'human_override', 'credit_approval', 'iris']:
    lm.advance('APP-NEW', svc)

next_tx = lm.get_next_tx('APP-NEW')
assert next_tx is None, 'all steps completed, next_tx should be None'

assert len(TX_TO_SERVICE) == 6, 'should have 6 tx mappings'
assert list(LIFECYCLE.keys()) == ['bdss', 'crss', 'ai_recommendation', 'human_override', 'credit_approval', 'iris']

print('lifecycle_manager: all assertions passed')
'@ 2>&1
Write-Host "$result"
if ($LASTEXITCODE -eq 0) { Test-Pass "lifecycle_manager" } else { Test-Fail "lifecycle_manager" }

# 5. Orchestrator with mock adapter
Write-Host ""
Write-Host "--- 5. Transaction Orchestrator: orchestrator (mock) ---"
$result = .\.venv\Scripts\python -c @'
import sys, os, tempfile
sys.path.insert(0, '02-transaction-orchestrator/app')

import transaction_queue as tq
tq.QUEUE_DIR = tq.BASE_DIR.parent / tempfile.mkdtemp()
tq.QUEUE_DIR.mkdir(parents=True, exist_ok=True)
import lifecycle_manager as lm_mod
lm_mod.STATE_DIR = lm_mod.BASE_DIR.parent / tempfile.mkdtemp()
lm_mod.STATE_DIR.mkdir(parents=True, exist_ok=True)

class MockAdapter:
    def __init__(self):
        self.events = []
    def submit_audit_event(self, audit_event):
        self.events.append(audit_event)
        return {'eventKey': 'TEST-KEY', 'txId': 'TEST-TX', 'status': 'COMMITTED'}
    def is_adapter_ready(self):
        return True
    def get_application_audit_history(self, application_id):
        return []

from transaction_queue import TransactionQueue
from lifecycle_manager import LifecycleManager
from orchestrator import Orchestrator

q = TransactionQueue()
lm = LifecycleManager()
mock = MockAdapter()
orch = Orchestrator(q, lm, mock)

q.enqueue('APP-MOCK', 'TX001', {'amount': 1000})
result = orch.process_batch()
assert result['processed'] == 1, 'should process 1 item'
assert result['results'][0]['status'] == 'completed', 'should complete successfully'
assert len(mock.events) == 1, 'should submit 1 audit event'
assert mock.events[0]['applicationId'] == 'APP-MOCK'
assert mock.events[0]['service'] == 'bdss'

result2 = orch.process_batch()
assert result2['status'] == 'idle', 'no more pending items'

print('orchestrator (mock): all assertions passed')
'@ 2>&1
Write-Host "$result"
if ($LASTEXITCODE -eq 0) { Test-Pass "orchestrator (mock)" } else { Test-Fail "orchestrator (mock)" }

# 6. Block Indexer — fabric_client mocks
Write-Host ""
Write-Host "--- 6. Block Indexer: indexer (mock) ---"
$result = .\.venv\Scripts\python -c @'
import sys, os
sys.path.insert(0, '07-block-indexer/app')

class MockFabricClient:
    def get_all_events(self):
        return [
            {'eventKey': 'AUDIT-TEST-001', 'submissionId': 'TEST-001', 'service': 'test', 'eventType': 'TEST'}
        ]

class MockMongoStore:
    def __init__(self):
        self.events = {}
    def get_indexed_keys(self):
        return set(self.events.keys())
    def upsert_event(self, event):
        self.events[event['eventKey']] = event
        return True
    def get_event_count(self):
        return len(self.events)

from indexer import BlockIndexer

mock_fabric = MockFabricClient()
mock_mongo = MockMongoStore()
indexer = BlockIndexer(fabric=mock_fabric, mongo=mock_mongo)

count = indexer.sync_once()
assert count == 1, 'should index 1 new event'

count2 = indexer.sync_once()
assert count2 == 0, 'should index 0 on second run (already indexed)'

assert mock_mongo.events['AUDIT-TEST-001']['service'] == 'test'

print('block indexer (mock): all assertions passed')
'@ 2>&1
Write-Host "$result"
if ($LASTEXITCODE -eq 0) { Test-Pass "block indexer (mock)" } else { Test-Fail "block indexer (mock)" }

# 7. Block Indexer — mongo_client connection
Write-Host ""
Write-Host "--- 7. Block Indexer: mongo_client import ---"
$result = .\.venv\Scripts\python -c @'
import sys
sys.path.insert(0, '07-block-indexer/app')
from mongo_client import MongoStore
print('MongoStore imported successfully')
'@ 2>&1
Write-Host "$result"
if ($LASTEXITCODE -eq 0) { Test-Pass "mongo_client import" } else { Test-Fail "mongo_client import" }

Write-Host ""
Write-Host "============================================"
Write-Host "  Results: $PASS passed, $FAIL failed"
Write-Host "============================================"

if ($FAIL -gt 0) { exit 1 }
