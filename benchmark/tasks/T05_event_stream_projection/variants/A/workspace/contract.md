# Atavism Task T05: Event Stream Projection Contract

## 1. System Overview
The `AccountProjector` service processes a stream of financial domain events to maintain current state projections for accounts. The engine operates completely in-memory, deterministically, and synchronously.

## 2. Account Lifecycle & Initialization
1. **Creation Sequence:** An account lifecycle begins with an `ACCOUNT_OPENED` event. The `sequence_id` of `ACCOUNT_OPENED` must be strictly `1`.
2. **Initial Balance & Projection State:** The opening event must specify a non-negative finite initial balance (`amount >= Decimal("0.00")`) having at most two fractional decimal places. An opened account initially has `balance = amount`, `is_frozen = False`, `last_applied_sequence = 1`, `pending_buffer_count = 0`, `is_blocked = False`, and `blocked_sequence_id = None`.
3. **Unopened Account Sequence Validation:** If an unopened account receives an `ACCOUNT_OPENED` event with `sequence_id > 1`, it violates the opening schema invariant (an account can only be opened at sequence ID 1) and MUST raise `EventValidationError`. It must not create partial account state or allocate pending buffers.
4. **Pre-Creation Non-Opening Event Rejection:** Any non-opening event (`FUNDS_DEPOSITED`, `FUNDS_WITHDRAWN`, `ACCOUNT_FROZEN`) received for an unopened account must fail immediately with `AccountNotOpenedError`, whether arriving with `sequence_id = 1` or `sequence_id > 1`.
5. **Reconciled Opening Duplicate & Reopening Rules:**
   - **Identical Opening Redelivery:** If an already-opened account receives an `ACCOUNT_OPENED` event with `sequence_id == 1` and an identical payload (matching initial balance and reason `None`), it is an idempotent duplicate. It must not alter state and returns the current `AccountProjection`.
   - **Conflicting Opening Payload at Sequence 1:** If an `ACCOUNT_OPENED` event arrives with `sequence_id == 1` but a conflicting payload (different initial balance or non-None reason), it must raise `ConflictingEventError`. State remains untouched.
   - **Reopening Prohibited:** Once created, an account can never be reopened. Any subsequent `ACCOUNT_OPENED` event received for an existing account with `sequence_id > 1` is an invalid attempt to reopen an account and MUST raise `AccountAlreadyOpenedError`.

## 3. Event Schema & Delivery Protocol

### 3.1 Typed Event Schema
Every event is an immutable `AccountEvent` instance with:
- `account_id` (`str`): Non-empty, non-whitespace string identifying the account.
- `event_type` (`EventType`): Enum value (`ACCOUNT_OPENED`, `FUNDS_DEPOSITED`, `FUNDS_WITHDRAWN`, `ACCOUNT_FROZEN`).
- `sequence_id` (`int`): Strictly positive integer ($1, 2, 3, \dots$). Python booleans (`True`/`False`) must be rejected with `EventValidationError`.
- `amount` (`Decimal | None`): Monetary quantity.
- `reason` (`str | None`): Textual explanation for freeze.

#### Per-EventType Field Rules
| Event Type | `sequence_id` Requirement | `amount` Requirement | `reason` Requirement | Validation Error on Violation |
| :--- | :--- | :--- | :--- | :--- |
| `ACCOUNT_OPENED` | Must be strictly `1` | Non-negative finite `Decimal` (`>= 0.00`) with at most two decimal places | Must be `None` | `EventValidationError` |
| `FUNDS_DEPOSITED` | Positive integer ($>= 2$) | Strictly positive finite `Decimal` (`> 0.00`) with at most two decimal places | Must be `None` | `EventValidationError` |
| `FUNDS_WITHDRAWN` | Positive integer ($>= 2$) | Strictly positive finite `Decimal` (`> 0.00`) with at most two decimal places | Must be `None` | `EventValidationError` |
| `ACCOUNT_FROZEN` | Positive integer ($>= 2$) | Must be `None` | Non-empty, non-whitespace `str` | `EventValidationError` |

Any unexpected field values (e.g. `amount` on `ACCOUNT_FROZEN`, `reason` on monetary events, or `sequence_id != 1` on `ACCOUNT_OPENED`) must raise `EventValidationError`. Silent normalization, trimming, or rounding is strictly prohibited.

### 3.2 Event Stream Delivery and Sequence Order Guarantees
The message transport guarantees **Strict FIFO, At-Least-Once Delivery**:
1. First-time delivery of new events for any given `account_id` must arrive in contiguous sequence order without gaps (`event.sequence_id == last_applied_sequence + 1`).
2. The projection engine must process applicable incoming events immediately.
3. Because delivery is at-least-once, previously delivered events may be redelivered at any time:
   - Identical redelivery of an already-applied event (`event.sequence_id <= last_applied_sequence`) must be ignored idempotently and return the current projection.
   - Conflicting redelivery of an already-applied sequence ID with a different payload must raise `ConflictingEventError`.
4. Any incoming new event with `event.sequence_id > last_applied_sequence + 1` violates the contiguous FIFO transport contract and MUST raise `InvalidEventSequenceError`. The event must not be applied, buffered, or stored.
5. Applicable event processing and domain error handling must strictly obey the Per-Event Atomicity and Blocked-Stream Failure Semantics defined in Section 5.

## 4. Monetary Precision & Arithmetic Rules
1. **Finite Decimal Representation:** All monetary values must be finite `Decimal` instances (`Decimal.is_finite() is True`). Non-finite Decimals (`NaN`, `Infinity`, `-Infinity`, `sNaN`) must be rejected with `EventValidationError`.
2. **Binary Float Rejection:** Binary floating-point values (`float`) must be strictly rejected with `EventValidationError`.
3. **At Most Two Fractional Decimal Places:** Monetary amounts may have at most two fractional decimal places.
4. **Excess Precision Rejection:** Values with more than two fractional decimal places (e.g. `Decimal("10.005")`, `Decimal("10.123")`) must be rejected with `EventValidationError`. Values with excess trailing zero precision beyond two fractional decimal places (e.g. `Decimal("10.000")`, where exponent `< -2`) are rejected as excess precision. Silent rounding, truncation, or normalization is strictly prohibited.
5. **Numerical Representation Equivalence:** Valid representations such as `Decimal("10")`, `Decimal("10.0")`, and `Decimal("10.00")` represent equivalent valid monetary values. An amount is valid if its exponent satisfies `d.as_tuple().exponent >= -2`.
6. **Overdraft Protection:** A withdrawal request with `amount > balance` must raise `InsufficientFundsError`. The balance, frozen state, and sequence number must not change.

## 5. Event Identity, Duplicate Delivery, and Blocked Stream Semantics

### 5.1 Event Tracking Domains
The projector maintains three conceptually separate tracking domains for each account:
1. **Observed Event Identity:** The immutable identity (event type, sequence ID, amount, reason) of every event ever observed for that account. This record persists permanently across buffer removal and domain failures.
2. **Pending-Buffer Membership:** Whether an uncommitted future event is currently waiting in the in-memory buffer for contiguous predecessors.
3. **Committed Event History:** The monotonically advancing sequence of events that successfully satisfied all domain preconditions and mutated projection state.

### 5.2 Observed Event Redelivery Behavior Matrix
| Lifecycle State of Observed Sequence ID | Identical Payload Redelivery | Conflicting Payload Redelivery |
| :--- | :--- | :--- |
| **Applied** (`sequence_id <= last_applied_sequence`) | **Ignore idempotently**: Return current `AccountProjection` without modifying state or balance. | **Reject**: Raise `ConflictingEventError`. Account state remains untouched. |
| **Pending in Buffer** (`sequence_id > last_applied_sequence + 1`, buffered) | **Ignore idempotently**: Return current `AccountProjection` without duplicate buffer insertion. | **Reject**: Raise `ConflictingEventError`. Buffer remains untouched. |
| **Blocked Sequence ID** (Removed from buffer upon domain precondition failure) | **Deterministic re-evaluation**: Re-evaluated against the current committed state; deterministically fails again with the same domain exception, leaving the account blocked (`is_blocked=True, blocked_sequence_id=sequence_id`). | **Reject**: Raise `ConflictingEventError`. Account state and buffer remain untouched. |

### 5.3 Blocked Stream Invariants and Causal Non-Bypass
1. **Stream Blockage:** When an applicable event fails a domain precondition (e.g. `InsufficientFundsError` on withdrawal or `AccountFrozenError` on deposit/withdrawal), the account enters an observable blocked state: `is_blocked = True`, `blocked_sequence_id = sequence_id`.
2. **Buffer Removal (Eviction):** The invalid event is removed from the pending buffer so that it does not loop infinitely during subsequent draining attempts. Removing the invalid event does NOT unblock the stream.
3. **Strict Causal Non-Bypass Invariant:** Later events (`sequence_id > blocked_sequence_id`) CANNOT bypass the failed sequence. In Treatment B, later events remain pending in the buffer and cannot be applied while the predecessor sequence is unresolved. In Control A, they are rejected as FIFO sequence gaps.
4. **Deterministic Retry Semantics:** The projector has no external state-changing recovery mechanism. An identical retry of a blocked sequence is re-evaluated against the unchanged committed projection state, reproduces the same domain exception, and leaves the account blocked.
5. **Behavior When New Events Arrive While Blocked:**
   - In Treatment B, identical retry re-evaluates and fails deterministically. Conflicting payloads are rejected with `ConflictingEventError`. Later future events are accepted into the pending buffer per normal identity rules, but cannot be applied. Duplicate future events do not duplicate buffer entries.
   - In Control A, future sequence gaps continue to be rejected per FIFO semantics.
6. **No Administrative Overrides:** Out-of-band administrative operations (such as force-applying, skipping, or payload rewriting) are strictly outside the scope of T05.

## 6. Account Isolation & Frozen Account Invariants
1. **Complete Partitioning:** Projection state is strictly partitioned per `account_id`. Each account maintains completely independent balance, frozen status, last applied sequence, pending buffer, observed event registry, and blocked status.
2. **Zero Cross-Account Leakage:** A gap, failure, duplicate, or buffer state in Account $A$ has zero effect on Account $B$. Events for multiple accounts may be interleaved in arbitrary order.
3. **Freeze Irreversibility:** When an `ACCOUNT_FROZEN` event commits, `is_frozen` transitions to `True`. An account cannot be unfrozen.
4. **Idempotent Freeze Delivery:** An identical duplicate `ACCOUNT_FROZEN` event is ignored idempotently.
5. **Monetary Operation Prohibition:** Any deposit or withdrawal event attempted on a frozen account must raise `AccountFrozenError`.
6. **Drain Order Security Rule:** A frozen account must never accept a monetary transaction simply because that transaction arrived out-of-order and was buffered before the freeze event was applied. When a buffer is drained, events are evaluated strictly in sequence order against the evolving state: if sequence $k$ freezes the account, sequence $k+1$ (monetary event) evaluated during the same drain fails with `AccountFrozenError` and blocks the stream at sequence $k+1$.
