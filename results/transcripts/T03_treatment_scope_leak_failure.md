# Representative Failure Transcript: Task T03 (Variant B)
**Research Dimension:** Multi-Tenant Isolation & Idempotency Key Scoping  
**Task ID:** `T03_tenant_idempotency`  
**Variant:** B (Treatment — Tenant-Scoped Namespace)  
**Failure Category:** `SCOPE_LEAK_AND_CROSS_TENANT_COLLISION`  

---

## 1. Context and Prompt Summary
The model is tasked with implementing `ReservationService` in `atavism_reservation/service.py`.
The authoritative specification `contract.md` in Variant B explicitly specifies:
```markdown
The idempotency key namespace is scoped per tenant: `(tenant_id, idempotency_key)`
- Different tenants may independently use identical idempotency keys without conflicting with each other.
- If Tenant B submits a request with an idempotency key that was already used by Tenant A,
  the service must treat it as an independent operation and allocate a new reservation.
```

---

## 2. Model Completion (Representative Extract)

```python
class ReservationService:
    def __init__(self, id_factory: Callable[[], str]) -> None:
        self.id_factory = id_factory
        # MODEL MISTAKE: Model implements a flat, global idempotency cache
        # instead of a composite (tenant_id, idempotency_key) namespace.
        self._idempotency_cache: dict[str, Reservation] = {}
        self._reservations: dict[str, Reservation] = {}

    def create_reservation(
        self,
        *,
        tenant_id: str,
        item_id: str,
        quantity: int,
        idempotency_key: str,
    ) -> Reservation:
        # Pretraining habit: lookup solely by idempotency_key
        if idempotency_key in self._idempotency_cache:
            existing = self._idempotency_cache[idempotency_key]
            # When Tenant B submits the same key used by Tenant A:
            if existing.tenant_id != tenant_id or existing.item_id != item_id or existing.quantity != quantity:
                raise IdempotencyConflict(f"Key {idempotency_key} already used with different payload")
            return existing

        res_id = self.id_factory()
        res = Reservation(reservation_id=res_id, tenant_id=tenant_id, item_id=item_id, quantity=quantity)
        self._idempotency_cache[idempotency_key] = res
        self._reservations[res_id] = res
        return res
```

---

## 3. Diagnostic Grader Verdict

```text
Grading Result: FAILED
  Total tests:  48
  Passed tests: 38
  Failed tests: 10
  Errors:       0

Diagnostics:
  [PASS] single_tenant_replay: 24/24 passed (100.0%)
  [PASS] payload_mismatch_conflict: 14/14 passed (100.0%)
  [FAIL] cross_tenant_isolation: 0/10 passed (0.0%)

Failures:
  [-] test_cross_tenant_identical_key_independent_success:
      IdempotencyConflict: Key 'req-123' already used with different payload
  [-] test_cross_tenant_key_does_not_consume_or_block:
      AssertionError: Expected 2 unique reservations across tenants, got 1
  [-] test_tenant_b_gets_independent_id_from_factory:
      AssertionError: id_factory called 1 times, expected 2
```

---

## 4. Why the Model Failed
The model correctly implemented single-tenant idempotency replay semantics and payload conflict detection. 

However, it failed because of **Premature Abstraction / Global State Bias**: In standard single-tenant web tutorials (e.g., Stripe-style single-merchant idempotency), `idempotency_key` is treated as a root-level primary key. The model failed to compose the compound key `(tenant_id, idempotency_key)` required by the multi-tenant contract. As a result, Tenant A's operation unexpectedly blocked Tenant B's completely valid request, representing a major multi-tenant denial-of-service / isolation violation.

