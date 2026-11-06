# Atavism T05 — Research Design: Asynchronous Protocol Invariant Preservation Under Out-of-Order Event Delivery

**Document Version:** 1.0.0-PROPOSAL (Design Only — Not Implemented)  
**Proposed Task ID:** `T05`  
**Proposed Task Title:** `Out-of-Order Event Stream Projection Protocol`  
**Research Dimension:** `Temporal Invariants and Asynchronous Protocol Adherence`  
**Benchmark Architect:** Senior AI Evaluation Researcher & Benchmark Architect  
**Status:** PROPOSED — Pending Human Approval Prior to Implementation  

---

## 1. Research Motivation & Candidate Direction Scoring

To extend Atavism beyond T01–T04, three candidate research directions were formulated and scored across seven methodology criteria (1–5 scale, max 35):

### Candidate Direction Evaluation Matrix

| Criteria (Weight: 1-5) | Direction 1: Incompatible Schema Evolution | Direction 2: Refactoring Contract Preservation | Direction 3: Out-of-Order Event Stream Projection |
| :--- | :---: | :---: | :---: |
| **1. Research Novelty** (relative to T01-T04) | 4 | 5 | **5** |
| **2. Real-World SE Relevance** | 5 | 5 | **5** |
| **3. Matched-Pair Isolation Feasibility** | 4 | 2 (High risk of structural churn) | **5 (Clean contract clause diff)** |
| **4. Objective Grading Feasibility** | 4 | 4 | **5 (Deterministic event traces)** |
| **5. Low Confounder Risk** | 4 | 3 | **4** |
| **6. Implementation Simplicity** | 4 | 4 | **4** |
| **7. Hackathon Judging Appeal** | 4 | 5 | **5** |
| **TOTAL SCORE** | **29 / 35** | **28 / 35** | **33 / 35 (SELECTED)** |

### Justification for Selected Direction (Direction 3)
In modern cloud architectures (Kafka, AWS EventBridge, SQS), event streams frequently deliver messages out of order due to network retries, parallel consumers, and partition rebalancing. LLMs trained heavily on simple procedural scripting often write state projection engines that assume **strict monotonic sequencing**, failing fatally or corrupting state when events arrive out of sequence. 

T05 evaluates whether an AI coding model can adhere to **asynchronous protocol contracts** where causal ordering must be maintained through deterministic buffering rather than naive in-order processing.

---

## 2. Research Question & Hypotheses

### 2.1 Central Research Question
> When an event stream contract transitions from guaranteed in-order FIFO delivery to out-of-order delivery, does an AI coding model implement causal buffering and replay invariants to preserve state consistency, or does it naively assume in-order arrival and fail when receiving out-of-sequence events?

### 2.2 Exploratory Hypotheses
- **Research Hypothesis ($H_1$):** Models evaluated on Treatment B will exhibit an "in-order arrival prior": despite contract specifications requiring causal buffering of future events, models will reject or drop out-of-order events (raising sequencing errors or dropping transitions) in a substantial proportion of zero-shot trials.
- **Null Hypothesis ($H_0$):** Under matched prompting conditions, AI coding models will demonstrate equal adherence to out-of-order buffering contracts as to in-order contracts without sequence regression.

---

## 3. Real-World Engineering Scenario

### 3.1 Domain: Financial Account Event Sourcing & Projection
A core ledger service processes an immutable stream of domain events for financial accounts:
- `AccountOpened(account_id, initial_balance, sequence_id)`
- `FundsDeposited(account_id, amount, sequence_id)`
- `FundsWithdrawn(account_id, amount, sequence_id)`
- `AccountFrozen(account_id, reason, sequence_id)`

Each event carries a strictly monotonic `sequence_id` ($1, 2, 3, \dots, N$) representing the authoritative causal history of the account.

### 3.2 The Operational Problem
- **In Control A:** The messaging infrastructure guarantees strict FIFO delivery per account. The projector can process events immediately as they arrive.
- **In Treatment B:** The messaging infrastructure is a distributed, partitioned bus where network retries and parallel delivery mean events may arrive out of order (e.g. sequence 3 arrives before sequence 2).
  - The projector must **not** drop sequence 3.
  - The projector must **not** apply sequence 3 before sequence 2 has been processed.
  - The projector must **buffer** out-of-order future events in an internal pending buffer and automatically apply them in strict causal sequence the moment the missing intermediate event arrives.
  - Duplicate events (events with `sequence_id <= current_applied_sequence`) must be idempotently ignored.

---

## 4. Matched-Pair Experimental Design

Following Atavism's strict **single-variable delta principle**, all model-visible files (`TASK.md`, `types.py`, starter `projector.py`) remain 100% byte-identical.

The **only** model-visible difference is Section 3.2 of `contract.md`:

### Control Variant A (`contract.md`, Section 3.2)
```markdown
### 3.2 Event Stream Ordering Guarantees
The message transport guarantees **Strict FIFO Monotonic Delivery**:
- Events for any given `account_id` arrive in strictly increasing sequence order without gaps (`sequence_id = current_sequence + 1`).
- The projection engine may process incoming events immediately upon arrival.
- Any event with `sequence_id <= current_sequence` is a duplicate and must be ignored.
```

### Treatment Variant B (`contract.md`, Section 3.2)
```markdown
### 3.2 Event Stream Ordering Guarantees
The message transport guarantees **At-Least-Once Out-of-Order Delivery**:
- Events for any given `account_id` may arrive out of sequence order (e.g., sequence 3 arrives before sequence 2).
- The projection engine MUST buffer future events (`sequence_id > current_sequence + 1`) in memory.
- When missing intermediate events arrive, all buffered consecutive events must be applied in strict sequence order.
- Any event with `sequence_id <= current_sequence` is a duplicate and must be ignored.
```

---

## 5. Starter Code and Interface Design

### 5.1 Domain Types (`src/atavism_projection/types.py`)
```python
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class EventType(str, Enum):
  ACCOUNT_OPENED = "ACCOUNT_OPENED"
  FUNDS_DEPOSITED = "FUNDS_DEPOSITED"
  FUNDS_WITHDRAWN = "FUNDS_WITHDRAWN"
  ACCOUNT_FROZEN = "ACCOUNT_FROZEN"


@dataclass(frozen=True)
class AccountEvent:
  account_id: str
  event_type: EventType
  amount: Decimal
  sequence_id: int


@dataclass(frozen=True)
class AccountProjection:
  account_id: str
  balance: Decimal
  is_frozen: bool
  last_applied_sequence: int
  pending_buffer_count: int


class ProjectionError(Exception):
  """Base exception."""


class InsufficientFundsError(ProjectionError):
  """Raised when a valid withdrawal exceeds balance."""


class InvalidEventSequenceError(ProjectionError):
  """Raised when an unrecoverable sequence anomaly occurs."""
```

### 5.2 Starter Code (`src/atavism_projection/projector.py`)
```python
class AccountProjector:
  """Processes events and maintains read-model projections in accordance with contract.md."""

  def __init__(self) -> None:
    pass

  def apply_event(self, event: AccountEvent) -> AccountProjection:
    """Applies an incoming event and returns the updated projection state."""
    raise NotImplementedError("AccountProjector.apply_event is not implemented")

  def get_projection(self, account_id: str) -> AccountProjection | None:
    """Returns the current projection for the specified account."""
    raise NotImplementedError(
        "AccountProjector.get_projection is not implemented"
    )
```

---

## 6. Diagnostic Test Categories & Evaluation Strategy

1. **`common_inorder_transitions` (Both A and B):**
   - Applies sequence 1, 2, 3 in order.
   - Verifies exact balance calculation with `Decimal`.
   - Verifies duplicate event deduplication (`sequence_id <= last_applied_sequence`).
2. **`common_validation` (Both A and B):**
   - Non-existent account withdrawal $\rightarrow$ `ProjectionError`.
   - Frozen account deposit/withdrawal $\rightarrow$ `ProjectionError`.
   - Insufficient funds withdrawal $\rightarrow$ `InsufficientFundsError`.
3. **`control_fifo_expectations` (Variant A Only):**
   - In Variant A, receiving a gap (`sequence_id > last_applied_sequence + 1`) violates transport guarantees; candidate raises `InvalidEventSequenceError`.
4. **`treatment_out_of_order_buffering` (Variant B Only):**
   - Receiving sequence 3 first: state remains at sequence 1, buffer count = 1.
   - Receiving sequence 2: state immediately advances through sequence 2 and sequence 3, buffer count returns to 0, balance reflects all three operations.
   - Multiple pending out-of-order events (sequences 4, 5, 3 arriving before 2).
   - Duplicate events arriving while buffer contains future events.

---

## 7. Reference Solutions and Mutation Strategy

### 7.1 Reference Solutions
1. `reference/control.py`: Strictly implements immediate sequential application and raises `InvalidEventSequenceError` on gaps.
2. `reference/treatment.py`: Implements a min-heap or sorted buffer of pending events per account, automatically draining consecutive sequences upon gap resolution.
3. `reference/alt_control.py`: Event-handler dispatch table architecture.
4. `reference/alt_treatment.py`: State-machine transition pipeline with priority queue buffering.

### 7.2 Mutation Strategy (7 Mutants Planned)
- `MutantDropFutureEvents`: Drops out-of-order events instead of buffering them.
- `MutantPrematureApplication`: Applies sequence 3 immediately without waiting for sequence 2.
- `MutantDuplicateReplay`: Re-applies duplicate sequence events.
- `MutantBufferLeak`: Fails to drain the buffer when the missing event arrives.
- `MutantFloatBalance`: Uses float arithmetic instead of `Decimal`.
- `MutantCrossAccountBufferLeak`: Shares pending event buffers across different `account_id`s.
- `MutantFrozenBypass`: Applies deposits to frozen accounts from buffered events.

---

## 8. Verification and Non-Implementation Guarantee

Per prompt constraints:
- **Zero T05 implementation files created.**
- **Zero repository code modified.**
- **Awaiting human approval before implementing T05.**

