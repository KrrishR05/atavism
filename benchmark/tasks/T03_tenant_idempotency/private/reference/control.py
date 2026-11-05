"""Reference implementation for T03 Variant A (Control: Global Idempotency Namespace)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from atavism_reservation.types import IdempotencyConflict, Reservation


def _validate_str(val: object, name: str) -> str:
    if not isinstance(val, str) or not val.strip():
        raise ValueError(f"{name} must be a non-empty, non-whitespace string, got: {val!r}")
    return val


def _validate_quantity(qty: object) -> int:
    if isinstance(qty, bool) or not isinstance(qty, int) or qty <= 0:
        raise ValueError(f"quantity must be a positive integer, got: {qty!r} (type {type(qty).__name__})")
    return qty


@dataclass(frozen=True)
class _IdempotencyRecord:
    tenant_id: str
    item_id: str
    quantity: int
    reservation: Reservation


class ReservationService:
    """Multi-tenant reservation service with a global idempotency namespace."""

    def __init__(self, id_factory: Callable[[], str]) -> None:
        self._id_factory = id_factory
        self._reservations: dict[str, Reservation] = {}
        # Global idempotency mapping: key -> _IdempotencyRecord
        self._idempotency: dict[str, _IdempotencyRecord] = {}

    def create_reservation(
        self,
        *,
        tenant_id: str,
        item_id: str,
        quantity: int,
        idempotency_key: str,
    ) -> Reservation:
        # 1. Validation happens BEFORE checking idempotency records
        v_tenant = _validate_str(tenant_id, "tenant_id")
        v_item = _validate_str(item_id, "item_id")
        v_key = _validate_str(idempotency_key, "idempotency_key")
        v_qty = _validate_quantity(quantity)

        # 2. Check global idempotency namespace
        if v_key in self._idempotency:
            record = self._idempotency[v_key]
            # Cross-tenant collision or payload conflict
            if record.tenant_id != v_tenant:
                raise IdempotencyConflict(
                    "Idempotency key has already been used by another tenant in the global namespace"
                )
            if record.item_id != v_item or record.quantity != v_qty:
                raise IdempotencyConflict(
                    "Idempotency key reused with conflicting request payload"
                )
            return record.reservation

        # 3. New reservation allocation
        res_id = self._id_factory()
        res = Reservation(
            reservation_id=res_id,
            tenant_id=v_tenant,
            item_id=v_item,
            quantity=v_qty,
        )

        # 4. Atomic state update
        self._reservations[res_id] = res
        self._idempotency[v_key] = _IdempotencyRecord(
            tenant_id=v_tenant,
            item_id=v_item,
            quantity=v_qty,
            reservation=res,
        )
        return res

    def get_reservation(
        self,
        *,
        tenant_id: str,
        reservation_id: str,
    ) -> Reservation | None:
        v_tenant = _validate_str(tenant_id, "tenant_id")
        v_res_id = _validate_str(reservation_id, "reservation_id")

        res = self._reservations.get(v_res_id)
        if res is None or res.tenant_id != v_tenant:
            return None
        return res

