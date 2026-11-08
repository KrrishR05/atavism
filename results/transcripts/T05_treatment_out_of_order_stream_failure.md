# Representative Failure Transcript: Task T05 (Variant B)
**Research Dimension:** Out-of-Order Event Stream Projection Protocol & Fail-Closed Draining  
**Task ID:** `T05_event_stream_projection`  
**Variant:** B (Treatment — Out-of-Order Buffered Delivery)  
**Failure Category:** `OUT_OF_ORDER_CORRUPTION_AND_DRAIN_LEAK`  

---

## 1. Context and Prompt Summary
The model is tasked with implementing `AccountProjectionEngine` in `atavism_stream/projection.py`.
The authoritative specification `contract.md` in Variant B explicitly stipulates:
```markdown
Transport guarantees At-Least-Once, Out-of-Order Delivery:
1. Any incoming event with `event.sequence_id > last_applied_sequence + 1` MUST be stored
   in an in-memory pending event buffer for that account.
2. It must NOT be applied to the balance or projection state until missing predecessor events arrive.
3. When the missing event arrives, apply it, then drain consecutive buffered events in strict sequence.
4. If a domain processing error occurs during buffer draining, the projection MUST fail closed,
   preserve the pending buffer, and flag `is_blocked = True`.
```

---

## 2. Model Completion (Representative Extract)

```python
class AccountProjectionEngine:
    def __init__(self) -> None:
        self.projections: dict[str, AccountProjection] = {}
        self.pending_buffers: dict[str, dict[int, AccountEvent]] = defaultdict(dict)

    def apply_event(self, event: AccountEvent) -> AccountProjection:
        proj = self._get_or_create(event.account_id)

        # MODEL MISTAKE: Model implements naive immediate application,
        # treating sequence_id merely as metadata rather than an ordering constraint.
        if event.sequence_id > proj.last_applied_sequence + 1:
            # Buffer event
            self.pending_buffers[event.account_id][event.sequence_id] = event
            return proj

        # Missing event arrives:
        proj = self._apply_single_event(proj, event)

        # Draining buffered events:
        next_seq = proj.last_applied_sequence + 1
        while next_seq in self.pending_buffers[event.account_id]:
            buffered_event = self.pending_buffers[event.account_id].pop(next_seq)
            try:
                proj = self._apply_single_event(proj, buffered_event)
            except DomainError as err:
                # MODEL MISTAKE: Model swallows domain error during buffer drain
                # or fails to set is_blocked = True, leaving account corrupted and active!
                pass
            next_seq += 1

        return proj
```

---

## 3. Diagnostic Grader Verdict

```text
Grading Result: FAILED
  Total tests:  62
  Passed tests: 47
  Failed tests: 15
  Errors:       0

Diagnostics:
  [PASS] contiguous_in_order_stream: 25/25 passed (100.0%)
  [PASS] decimal_precision: 12/12 passed (100.0%)
  [PASS] idempotent_deduplication: 10/10 passed (100.0%)
  [FAIL] out_of_order_buffering: 0/7 passed (0.0%)
  [FAIL] drain_failure_atomicity_and_blocking: 0/8 passed (0.0%)

Failures:
  [-] test_out_of_order_debit_buffered_until_credit_arrives:
      AssertionError: Expected balance Decimal('100.00'), got Decimal('-50.00') (applied premature debit)
  [-] test_drain_domain_failure_sets_is_blocked_true:
      AssertionError: assert False is True (account.is_blocked remained False after domain drain failure)
  [-] test_failed_drain_preserves_remaining_buffer:
      AssertionError: Pending buffer was emptied despite unrecoverable drain failure
```

---

## 4. Why the Model Failed
The model successfully mastered standard in-order event application, basic Decimal balance tracking, and redelivered event deduplication.

However, it failed because of **Distributed State Asynchrony Blindness & Improper Error Recovery**: Most code in pretraining data processes streams assuming synchronous or strictly in-order message delivery (or relies on external frameworks like Kafka or Flink to handle ordering). When required to implement stateful reordering and fail-closed atomicity inside an in-memory projection engine, the model took shortcuts: it popped buffered events before verifying their atomic application, and swallowed drain errors rather than preserving the unapplied buffer and locking the account with `is_blocked = True`. In distributed banking and settlement ledgers, this causes negative overdraft anomalies and permanent ledger divergence.

