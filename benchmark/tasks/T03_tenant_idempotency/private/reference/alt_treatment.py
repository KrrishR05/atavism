"""Alternative valid reference implementation for T03 Variant B (Treatment).

Architecturally distinct: uses an encapsulated repository and per-tenant idempotency registry pattern.
"""

from __future__ import annotations

from typing import Callable, NamedTuple

from atavism_reservation.types import IdempotencyConflict, Reservation


class _Payload(NamedTuple):
    item_id: str
    quantity: int


class ReservationRepository:
    """Encapsulated storage for reservations partitioned by tenant."""

    def __init__(self) -> None:
        self._by_id: dict[str, Reservation] = {}

    def save(self, reservation: Reservation) -> None:
        self._by_id[reservation.reservation_id] = reservation

    def find(self, tenant_id: str, reservation_id: str) -> Reservation | None:
        res = self._by_id.get(reservation_id)
        if res is not None and res.tenant_id == tenant_id:
            return res
        return None


class TenantScopedIdempotencyRegistry:
    """Per-tenant idempotency registry where key is scoped strictly to tenant_id."""

    def __init__(self) -> None:
        # tenant_id -> key -> (payload, reservation)
        self._partitions: dict[str, dict[str, tuple[_Payload, Reservation]]] = {}

    def get_or_check(
        self,
        tenant_id: str,
        key: str,
        payload: _Payload,
    ) -> Reservation | None:
        tenant_scope = self._partitions.get(tenant_id)
        if tenant_scope is None or key not in tenant_scope:
            return None

        registered_payload, reservation = tenant_scope[key]
        if registered_payload != payload:
            raise IdempotencyConflict(
                "Payload mismatch for existing idempotency key in tenant scope"
            )
        return reservation

    def register(
        self,
        tenant_id: str,
        key: str,
        payload: _Payload,
        reservation: Reservation,
    ) -> None:
        if tenant_id not in self._partitions:
            self._partitions[tenant_id] = {}
        self._partitions[tenant_id][key] = (payload, reservation)


class ReservationService:
    """Alternative implementation of ReservationService for Variant B."""

    def __init__(self, id_factory: Callable[[], str]) -> None:
        self._id_factory = id_factory
        self._repo = ReservationRepository()
        self._registry = TenantScopedIdempotencyRegistry()

    @staticmethod
    def _validate_inputs(tenant_id: object, item_id: object, quantity: object, key: object) -> tuple[str, str, int, str]:
        for val, name in ((tenant_id, "tenant_id"), (item_id, "item_id"), (key, "idempotency_key")):
            if not isinstance(val, str) or not val.strip():
                raise ValueError(f"Invalid {name}: {val!r}")

        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
            raise ValueError(f"Invalid quantity: {quantity!r}")

        return str(tenant_id), str(item_id), int(quantity), str(key)

    def create_reservation(
        self,
        *,
        tenant_id: str,
        item_id: str,
        quantity: int,
        idempotency_key: str,
    ) -> Reservation:
        t_id, i_id, qty, ikey = self._validate_inputs(tenant_id, item_id, quantity, idempotency_key)
        payload = _Payload(i_id, qty)

        existing = self._registry.get_or_check(t_id, ikey, payload)
        if existing is not None:
            return existing

        new_id = self._id_factory()
        res = Reservation(reservation_id=new_id, tenant_id=t_id, item_id=i_id, quantity=qty)

        self._repo.save(res)
        self._registry.register(t_id, ikey, payload, res)
        return res

    def get_reservation(
        self,
        *,
        tenant_id: str,
        reservation_id: str,
    ) -> Reservation | None:
        if not isinstance(tenant_id, str) or not tenant_id.strip():
            raise ValueError(f"Invalid tenant_id: {tenant_id!r}")
        if not isinstance(reservation_id, str) or not reservation_id.strip():
            raise ValueError(f"Invalid reservation_id: {reservation_id!r}")

        return self._repo.find(tenant_id, reservation_id)

