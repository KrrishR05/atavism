# Meridian Gateway Reservation Service Contract

**Document Version:** 1.0.0  
**Authority:** Authoritative Specification  

This document specifies the normative behavioral requirements for the `ReservationService`. All implementations must comply with every clause defined herein.

---

## 1. System Overview

The `ReservationService` is an in-memory multi-tenant reservation coordinator. Clients submit requests with an authenticated tenant identifier and an idempotency key to create reservations safely across network retries.

---

## 2. Input Validation

All parameters must be validated before checking idempotency records or mutating service state.

### 2.1 String Fields
- `tenant_id`, `item_id`, and `idempotency_key` must be non-empty strings (`str`).
- Strings containing only whitespace (e.g. `"   "`, `"\t"`, `"\n"`) are invalid.
- Non-string types (e.g. `None`, numbers, objects) are invalid.
- Original string values must be preserved exactly as passed. Implementations must **not** silently strip or normalize whitespace.
- If any string parameter is invalid, the service must raise `ValueError`.

### 2.2 Numeric Fields
- `quantity` must be a positive integer (`quantity > 0`).
- Non-integer numeric types (such as `float`) are invalid and must raise `ValueError`.
- Python boolean values (`True`, `False`) must **not** be accepted as valid quantities, despite `bool` being a subclass of `int`. Passing a boolean for `quantity` must raise `ValueError`.
- Non-positive integers (`quantity <= 0`) must raise `ValueError`.

### 2.3 Retrieval Parameters
- In `get_reservation(*, tenant_id: str, reservation_id: str)`, both `tenant_id` and `reservation_id` must be non-empty, non-whitespace strings.
- If either parameter is invalid, `get_reservation` must raise `ValueError`.

### 2.4 Precedence and State Protection
- Validation must occur **before** existing idempotency records are inspected or returned. A replayed request with an invalid field (e.g., `quantity=0`) must raise `ValueError` rather than returning a previously created reservation.
- Invalid requests must not mutate stored state or consume an identifier from `id_factory`.

---

## 3. Identifier Allocation

- The service receives an `id_factory: Callable[[], str]` upon initialization.
- For each **newly created reservation**, the service must invoke `id_factory` exactly once to obtain the `reservation_id`.
- The service must **not** call `id_factory` during:
  - Idempotent replays.
  - Idempotency conflicts (`IdempotencyConflict`).
  - Validation failures (`ValueError`).
- The new reservation record must only be committed to storage after all validations and idempotency checks pass.

---

## 4. Basic Idempotency & Replay Semantics

The request payload consists of:
```python
(item_id, quantity)
```

When a request arrives with an existing key within the applicable idempotency namespace:

1. **Exact Replay:** If the request originates from the same tenant and provides an equivalent payload `(item_id, quantity)`, the service must return the existing `Reservation` instance.
2. **Payload Conflict:** If the request provides a conflicting payload (different `item_id` or different `quantity`), the service must raise `IdempotencyConflict`.
3. **No Side Effects:** An exact replay must not allocate a new identifier, create another reservation record, or alter existing records.
4. **State Immutability:** An `IdempotencyConflict` must not overwrite, mutate, or delete existing reservation records or idempotency registrations.

---

## 5. Tenant Isolation

1. **Resource Access:** A tenant may retrieve only reservations that belong to that tenant.
2. **Non-Existent & Cross-Tenant Lookups:**
   - Querying an unknown `reservation_id` must return `None`.
   - Querying a `reservation_id` belonging to a different tenant must return `None`.
3. **Information Concealment:** The service must never disclose another tenant's reservation details, existence, or status through `get_reservation`.
4. **Independent Retrieval:** Multiple tenants with reservations for the same `item_id` remain strictly partitioned.

---

## 6. Idempotency Key Scope

The idempotency key namespace is **scoped per tenant**:

```python
(tenant_id, idempotency_key)
```

- An idempotency key is unique only within the context of the requesting tenant.
- Different tenants may independently use identical idempotency keys without conflicting with each other.
- If Tenant B submits a request with an idempotency key that was already used by Tenant A, the service must treat it as an independent operation, allocate a new reservation identifier from `id_factory`, and store it under Tenant B's namespace.
- An idempotency conflict or replay in Tenant A has no effect on Tenant B's operations using the same key.
- Each tenant can independently replay or trigger payload conflicts within its own tenant-scoped namespace.

---

## 7. State Integrity

- Every successful new operation creates exactly one `Reservation`.
- All stored reservations are immutable once created.
- Operations that raise exceptions (`ValueError`, `IdempotencyConflict`, or errors raised by `id_factory`) must leave the service in a clean, unmutated state.

