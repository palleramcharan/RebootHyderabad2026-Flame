# Example: Application APP-1001

Suppose a customer submits a loan application.

- **Application ID**: APP-1001
- **Customer**: Rajesh Kumar

The application moves through your workflow:

```
BDSS
  │
  ▼
Document Verification
  │
  ▼
AI Risk Assessment
  │
  ▼
Credit Decision
  │
  ▼
Manager Approval
  │
  ▼
Disbursement
```

Every completed stage generates one audit event.

---

### Block 100

At 10:00 AM the application is submitted.

```
Block #100
------------------------------------------------

Transaction 1
Application : APP-1001
Event       : APPLICATION_SUBMITTED
WorkflowStep: TX001
Service     : BDSS
TxID        : A1B2C3

Transaction 2
Application : APP-1002
Event       : APPLICATION_SUBMITTED

Transaction 3
Application : APP-1003
Event       : APPLICATION_SUBMITTED
```

---

### Block 101

Five minutes later documents are verified.

```
Block #101
------------------------------------------------

Transaction 1
Application : APP-1001
Event       : DOCUMENT_VERIFIED
WorkflowStep: TX002
Service     : Verification
TxID        : D4E5F6

Transaction 2
Application : APP-1005
Event       : APPLICATION_SUBMITTED
```

---

### Block 103

AI completes the risk assessment.

```
Block #103
------------------------------------------------

Transaction 1
Application : APP-1007
Event       : APPLICATION_SUBMITTED

Transaction 2
Application : APP-1001
Event       : AI_RISK_COMPLETED
WorkflowStep: TX003
Service     : AI
TxID        : G7H8I9

Transaction 3
Application : APP-1008
Event       : DOCUMENT_VERIFIED
```

---

### Block 107

Credit decision.

```
Block #107
------------------------------------------------

Transaction 1
Application : APP-1001
Event       : CREDIT_APPROVED
WorkflowStep: TX004
Service     : Credit
TxID        : J1K2L3
```

---

### Block 112

Manager approval.

```
Block #112
------------------------------------------------

Transaction 1
Application : APP-1001
Event       : MANAGER_APPROVED
WorkflowStep: TX005
Service     : Manager
TxID        : M4N5O6
```

---

### Block 120

Loan disbursed.

```
Block #120
------------------------------------------------

Transaction 1
Application : APP-1001
Event       : LOAN_DISBURSED
WorkflowStep: TX006
Service     : Finance
TxID        : P7Q8R9
```

---

## What the blockchain contains

```
                    BLOCKCHAIN

Block100
├── APP-1001  APPLICATION_SUBMITTED
├── APP-1002
└── APP-1003

Block101
├── APP-1001  DOCUMENT_VERIFIED
└── APP-1005

Block102
├── APP-1010
└── APP-1009

Block103
├── APP-1007
├── APP-1001  AI_RISK_COMPLETED
└── APP-1008

Block104
...

Block107
└── APP-1001  CREDIT_APPROVED

Block112
└── APP-1001  MANAGER_APPROVED

Block120
└── APP-1001  LOAN_DISBURSED
```

Notice that APP-1001 appears in six different blocks. That's completely normal.

---
