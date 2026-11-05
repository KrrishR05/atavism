# Task T03: Tenant Isolation and Idempotency Scope

## 1. Overview

You are implementing a core component of a multi-tenant reservation service for Meridian Gateway.

In multi-tenant cloud architectures, services must simultaneously guarantee two critical properties:
1. **Tenant Isolation:** Tenants must never access, view, or mutate resources belonging to another tenant.
2. **Operation Idempotency:** Clients provide an idempotency key to prevent accidental duplicate creations during network retries or replays.

Your objective is to implement the `ReservationService` class in `src/atavism_reservation/service.py` according to the explicit technical specifications defined in `contract.md`.

---

## 2. Workspace File Structure

```text
.
├── TASK.md                           # This overview and instructional document
├── contract.md                       # Authoritative technical specification
└── src/
    └── atavism_reservation/
        ├── __init__.py               # Package exports
        ├── types.py                  # Domain models and exceptions (read-only)
        └── service.py                # Candidate implementation target
```

---

## 3. Public API Specification

Your implementation must expose `ReservationService` matching the class structure in `src/atavism_reservation/service.py`:

```python
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Reservation:
    reservation_id: str
    tenant_id: str
    item_id: str
    quantity: int


class IdempotencyConflict(Exception):
    pass


class ReservationService:
    def __init__(
        self,
        id_factory: Callable[[], str],
    ) -> None:
        ...

    def create_reservation(
        self,
        *,
        tenant_id: str,
        item_id: str,
        quantity: int,
        idempotency_key: str,
    ) -> Reservation:
        ...

    def get_reservation(
        self,
        *,
        tenant_id: str,
        reservation_id: str,
    ) -> Reservation | None:
        ...
```

---

## 4. Key Constraints

- **Authoritative Contract:** `contract.md` contains the normative requirements for input validation, identifier allocation, idempotency handling, tenant isolation, and namespace scope.
- **Identifier Generation:** You must invoke `id_factory` exactly once for each newly created reservation. Do not generate random identifiers internally or use UUIDs directly.
- **In-Memory Operation:** Do not use external network calls, file system persistence, or databases. The service is purely in-memory.
- **Strict Keyword-Only Arguments:** Notice that `create_reservation` and `get_reservation` enforce keyword-only arguments (`*`).

