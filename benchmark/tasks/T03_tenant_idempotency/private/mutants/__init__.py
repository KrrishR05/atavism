"""Deliberately flawed candidate implementations (mutants) for T03.

Each mutant introduces exactly one architectural or behavioral defect to verify
that the hidden test suites reject faulty candidates with descriptive failure reasons.
"""

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
        raise ValueError(f"quantity must be a positive integer, got: {qty!r}")
    return qty


@dataclass(frozen=True)
class _IdempotencyRecord:
    tenant_id: str
    item_id: str
    quantity: int
    reservation: Reservation


# 1. Global-key mutant: Uses raw idempotency keys in treatment (T03-B) instead of tenant-scoped keys
class MutantGlobalKeyService:
    """Mutant 1: Ignores tenant scoping for idempotency keys; uses raw global key in Treatment."""

    def __init__(self, id_factory: Callable[[], str]) -> None:
        self._id_factory = id_factory
        self._reservations: dict[str, Reservation] = {}
        self._idempotency: dict[str, _IdempotencyRecord] = {}

    def create_reservation(self, *, tenant_id: str, item_id: str, quantity: int, idempotency_key: str) -> Reservation:
        v_tenant = _validate_str(tenant_id, "tenant_id")
        v_item = _validate_str(item_id, "item_id")
        v_key = _validate_str(idempotency_key, "idempotency_key")
        v_qty = _validate_quantity(quantity)

        # Defect: Uses global raw key even in Treatment
        if v_key in self._idempotency:
            record = self._idempotency[v_key]
            if record.tenant_id != v_tenant:
                raise IdempotencyConflict("Global collision across tenants")
            if record.item_id != v_item or record.quantity != v_qty:
                raise IdempotencyConflict("Payload conflict")
            return record.reservation

        res_id = self._id_factory()
        res = Reservation(res_id, v_tenant, v_item, v_qty)
        self._reservations[res_id] = res
        self._idempotency[v_key] = _IdempotencyRecord(v_tenant, v_item, v_qty, res)
        return res

    def get_reservation(self, *, tenant_id: str, reservation_id: str) -> Reservation | None:
        v_tenant = _validate_str(tenant_id, "tenant_id")
        v_res_id = _validate_str(reservation_id, "reservation_id")
        res = self._reservations.get(v_res_id)
        if res is None or res.tenant_id != v_tenant:
            return None
        return res


# 2. Tenant-ignored mutant: Omits tenant check during reservation retrieval
class MutantTenantIgnoredService:
    """Mutant 2: Omits tenant ownership check in get_reservation, leaking cross-tenant records."""

    def __init__(self, id_factory: Callable[[], str]) -> None:
        self._id_factory = id_factory
        self._reservations: dict[str, Reservation] = {}
        self._idempotency: dict[str, _IdempotencyRecord] = {}

    def create_reservation(self, *, tenant_id: str, item_id: str, quantity: int, idempotency_key: str) -> Reservation:
        v_tenant = _validate_str(tenant_id, "tenant_id")
        v_item = _validate_str(item_id, "item_id")
        v_key = _validate_str(idempotency_key, "idempotency_key")
        v_qty = _validate_quantity(quantity)

        if v_key in self._idempotency:
            record = self._idempotency[v_key]
            if record.tenant_id != v_tenant:
                raise IdempotencyConflict("Cross tenant collision")
            if record.item_id != v_item or record.quantity != v_qty:
                raise IdempotencyConflict("Payload mismatch")
            return record.reservation

        res_id = self._id_factory()
        res = Reservation(res_id, v_tenant, v_item, v_qty)
        self._reservations[res_id] = res
        self._idempotency[v_key] = _IdempotencyRecord(v_tenant, v_item, v_qty, res)
        return res

    def get_reservation(self, *, tenant_id: str, reservation_id: str) -> Reservation | None:
        _validate_str(tenant_id, "tenant_id")
        v_res_id = _validate_str(reservation_id, "reservation_id")
        # Defect: Returns reservation regardless of tenant ownership
        return self._reservations.get(v_res_id)


# 3. Payload-blind mutant: Returns previous result even when payload changes
class MutantPayloadBlindService:
    """Mutant 3: Fails to detect payload conflict; blindly returns previous reservation."""

    def __init__(self, id_factory: Callable[[], str]) -> None:
        self._id_factory = id_factory
        self._reservations: dict[str, Reservation] = {}
        self._idempotency: dict[str, _IdempotencyRecord] = {}

    def create_reservation(self, *, tenant_id: str, item_id: str, quantity: int, idempotency_key: str) -> Reservation:
        v_tenant = _validate_str(tenant_id, "tenant_id")
        v_item = _validate_str(item_id, "item_id")
        v_key = _validate_str(idempotency_key, "idempotency_key")
        v_qty = _validate_quantity(quantity)

        if v_key in self._idempotency:
            record = self._idempotency[v_key]
            if record.tenant_id != v_tenant:
                raise IdempotencyConflict("Cross tenant collision")
            # Defect: Does not check if item_id or quantity changed!
            return record.reservation

        res_id = self._id_factory()
        res = Reservation(res_id, v_tenant, v_item, v_qty)
        self._reservations[res_id] = res
        self._idempotency[v_key] = _IdempotencyRecord(v_tenant, v_item, v_qty, res)
        return res

    def get_reservation(self, *, tenant_id: str, reservation_id: str) -> Reservation | None:
        v_tenant = _validate_str(tenant_id, "tenant_id")
        v_res_id = _validate_str(reservation_id, "reservation_id")
        res = self._reservations.get(v_res_id)
        if res is None or res.tenant_id != v_tenant:
            return None
        return res


# 4. Duplicate-creation mutant: Creates a new reservation on every repeated request
class MutantDuplicateCreationService:
    """Mutant 4: Ignores idempotency and creates a new reservation on every call."""

    def __init__(self, id_factory: Callable[[], str]) -> None:
        self._id_factory = id_factory
        self._reservations: dict[str, Reservation] = {}

    def create_reservation(self, *, tenant_id: str, item_id: str, quantity: int, idempotency_key: str) -> Reservation:
        v_tenant = _validate_str(tenant_id, "tenant_id")
        v_item = _validate_str(item_id, "item_id")
        _validate_str(idempotency_key, "idempotency_key")
        v_qty = _validate_quantity(quantity)

        # Defect: Always creates a new reservation, ignoring key
        res_id = self._id_factory()
        res = Reservation(res_id, v_tenant, v_item, v_qty)
        self._reservations[res_id] = res
        return res

    def get_reservation(self, *, tenant_id: str, reservation_id: str) -> Reservation | None:
        v_tenant = _validate_str(tenant_id, "tenant_id")
        v_res_id = _validate_str(reservation_id, "reservation_id")
        res = self._reservations.get(v_res_id)
        if res is None or res.tenant_id != v_tenant:
            return None
        return res


# 5. Replay-allocation mutant: Consumes a new identifier from id_factory on replay
class MutantReplayAllocationService:
    """Mutant 5: Calls id_factory on idempotent replay, consuming identifiers."""

    def __init__(self, id_factory: Callable[[], str]) -> None:
        self._id_factory = id_factory
        self._reservations: dict[str, Reservation] = {}
        self._idempotency: dict[str, _IdempotencyRecord] = {}

    def create_reservation(self, *, tenant_id: str, item_id: str, quantity: int, idempotency_key: str) -> Reservation:
        v_tenant = _validate_str(tenant_id, "tenant_id")
        v_item = _validate_str(item_id, "item_id")
        v_key = _validate_str(idempotency_key, "idempotency_key")
        v_qty = _validate_quantity(quantity)

        if v_key in self._idempotency:
            record = self._idempotency[v_key]
            if record.tenant_id != v_tenant:
                raise IdempotencyConflict("Cross tenant collision")
            if record.item_id != v_item or record.quantity != v_qty:
                raise IdempotencyConflict("Payload conflict")
            # Defect: Unnecessarily calls id_factory on replay
            _ = self._id_factory()
            return record.reservation

        res_id = self._id_factory()
        res = Reservation(res_id, v_tenant, v_item, v_qty)
        self._reservations[res_id] = res
        self._idempotency[v_key] = _IdempotencyRecord(v_tenant, v_item, v_qty, res)
        return res

    def get_reservation(self, *, tenant_id: str, reservation_id: str) -> Reservation | None:
        v_tenant = _validate_str(tenant_id, "tenant_id")
        v_res_id = _validate_str(reservation_id, "reservation_id")
        res = self._reservations.get(v_res_id)
        if res is None or res.tenant_id != v_tenant:
            return None
        return res


# 6. Conflict-mutation mutant: Changes stored state before raising a conflict
class MutantConflictMutationService:
    """Mutant 6: Mutates stored reservation state when a payload conflict occurs."""

    def __init__(self, id_factory: Callable[[], str]) -> None:
        self._id_factory = id_factory
        self._reservations: dict[str, Reservation] = {}
        self._idempotency: dict[str, _IdempotencyRecord] = {}

    def create_reservation(self, *, tenant_id: str, item_id: str, quantity: int, idempotency_key: str) -> Reservation:
        v_tenant = _validate_str(tenant_id, "tenant_id")
        v_item = _validate_str(item_id, "item_id")
        v_key = _validate_str(idempotency_key, "idempotency_key")
        v_qty = _validate_quantity(quantity)

        if v_key in self._idempotency:
            record = self._idempotency[v_key]
            if record.tenant_id != v_tenant:
                raise IdempotencyConflict("Cross tenant collision")
            if record.item_id != v_item or record.quantity != v_qty:
                # Defect: Corrupts stored reservation before raising conflict!
                mutated = Reservation(record.reservation.reservation_id, v_tenant, v_item, v_qty)
                self._reservations[record.reservation.reservation_id] = mutated
                raise IdempotencyConflict("Payload conflict")
            return record.reservation

        res_id = self._id_factory()
        res = Reservation(res_id, v_tenant, v_item, v_qty)
        self._reservations[res_id] = res
        self._idempotency[v_key] = _IdempotencyRecord(v_tenant, v_item, v_qty, res)
        return res

    def get_reservation(self, *, tenant_id: str, reservation_id: str) -> Reservation | None:
        v_tenant = _validate_str(tenant_id, "tenant_id")
        v_res_id = _validate_str(reservation_id, "reservation_id")
        res = self._reservations.get(v_res_id)
        if res is None or res.tenant_id != v_tenant:
            return None
        return res


# 7. Validation-order mutant: Returns an existing result before validating incoming request
class MutantValidationOrderService:
    """Mutant 7: Checks idempotency before input validation; replayed invalid request succeeds."""

    def __init__(self, id_factory: Callable[[], str]) -> None:
        self._id_factory = id_factory
        self._reservations: dict[str, Reservation] = {}
        self._idempotency: dict[str, _IdempotencyRecord] = {}

    def create_reservation(self, *, tenant_id: str, item_id: str, quantity: int, idempotency_key: str) -> Reservation:
        # Defect: Checks idempotency before validation!
        if isinstance(idempotency_key, str) and idempotency_key in self._idempotency:
            record = self._idempotency[idempotency_key]
            # Returns existing reservation without validating quantity or item_id!
            return record.reservation

        v_tenant = _validate_str(tenant_id, "tenant_id")
        v_item = _validate_str(item_id, "item_id")
        v_key = _validate_str(idempotency_key, "idempotency_key")
        v_qty = _validate_quantity(quantity)

        res_id = self._id_factory()
        res = Reservation(res_id, v_tenant, v_item, v_qty)
        self._reservations[res_id] = res
        self._idempotency[v_key] = _IdempotencyRecord(v_tenant, v_item, v_qty, res)
        return res

    def get_reservation(self, *, tenant_id: str, reservation_id: str) -> Reservation | None:
        v_tenant = _validate_str(tenant_id, "tenant_id")
        v_res_id = _validate_str(reservation_id, "reservation_id")
        res = self._reservations.get(v_res_id)
        if res is None or res.tenant_id != v_tenant:
            return None
        return res


# 8. Boolean-quantity mutant: Accepts True as a valid quantity
class MutantBooleanQuantityService:
    """Mutant 8: Accepts bool as int because bool is a subclass of int in Python."""

    def __init__(self, id_factory: Callable[[], str]) -> None:
        self._id_factory = id_factory
        self._reservations: dict[str, Reservation] = {}
        self._idempotency: dict[str, _IdempotencyRecord] = {}

    def create_reservation(self, *, tenant_id: str, item_id: str, quantity: int, idempotency_key: str) -> Reservation:
        v_tenant = _validate_str(tenant_id, "tenant_id")
        v_item = _validate_str(item_id, "item_id")
        v_key = _validate_str(idempotency_key, "idempotency_key")

        # Defect: isinstance(True, int) is True; does not check not isinstance(qty, bool)!
        if not isinstance(quantity, int) or quantity <= 0:
            raise ValueError(f"Invalid quantity: {quantity!r}")
        v_qty = quantity

        if v_key in self._idempotency:
            record = self._idempotency[v_key]
            if record.tenant_id != v_tenant:
                raise IdempotencyConflict("Cross tenant collision")
            if record.item_id != v_item or record.quantity != v_qty:
                raise IdempotencyConflict("Payload conflict")
            return record.reservation

        res_id = self._id_factory()
        res = Reservation(res_id, v_tenant, v_item, v_qty)
        self._reservations[res_id] = res
        self._idempotency[v_key] = _IdempotencyRecord(v_tenant, v_item, v_qty, res)
        return res

    def get_reservation(self, *, tenant_id: str, reservation_id: str) -> Reservation | None:
        v_tenant = _validate_str(tenant_id, "tenant_id")
        v_res_id = _validate_str(reservation_id, "reservation_id")
        res = self._reservations.get(v_res_id)
        if res is None or res.tenant_id != v_tenant:
            return None
        return res


# 9. Cross-tenant-leak mutant: In Control, returns another tenant's reservation during an idempotency collision
class MutantCrossTenantLeakService:
    """Mutant 9: In global namespace, returns existing reservation to foreign tenant instead of raising conflict."""

    def __init__(self, id_factory: Callable[[], str]) -> None:
        self._id_factory = id_factory
        self._reservations: dict[str, Reservation] = {}
        self._idempotency: dict[str, _IdempotencyRecord] = {}

    def create_reservation(self, *, tenant_id: str, item_id: str, quantity: int, idempotency_key: str) -> Reservation:
        v_tenant = _validate_str(tenant_id, "tenant_id")
        v_item = _validate_str(item_id, "item_id")
        v_key = _validate_str(idempotency_key, "idempotency_key")
        v_qty = _validate_quantity(quantity)

        if v_key in self._idempotency:
            record = self._idempotency[v_key]
            # Defect: Returns the reservation even if tenant_id does not match!
            if record.item_id == v_item and record.quantity == v_qty:
                return record.reservation
            raise IdempotencyConflict("Payload conflict")

        res_id = self._id_factory()
        res = Reservation(res_id, v_tenant, v_item, v_qty)
        self._reservations[res_id] = res
        self._idempotency[v_key] = _IdempotencyRecord(v_tenant, v_item, v_qty, res)
        return res

    def get_reservation(self, *, tenant_id: str, reservation_id: str) -> Reservation | None:
        v_tenant = _validate_str(tenant_id, "tenant_id")
        v_res_id = _validate_str(reservation_id, "reservation_id")
        res = self._reservations.get(v_res_id)
        if res is None or res.tenant_id != v_tenant:
            return None
        return res


# 10. Tenant-key-collision mutant: Incorrectly shares idempotency state across tenants in Treatment
class MutantTenantKeyCollisionService:
    """Mutant 10: In treatment, blocks cross-tenant usage by raising conflict on duplicate key."""

    def __init__(self, id_factory: Callable[[], str]) -> None:
        self._id_factory = id_factory
        self._reservations: dict[str, Reservation] = {}
        self._idempotency: dict[tuple[str, str], _IdempotencyRecord] = {}
        self._all_keys: set[str] = set()

    def create_reservation(self, *, tenant_id: str, item_id: str, quantity: int, idempotency_key: str) -> Reservation:
        v_tenant = _validate_str(tenant_id, "tenant_id")
        v_item = _validate_str(item_id, "item_id")
        v_key = _validate_str(idempotency_key, "idempotency_key")
        v_qty = _validate_quantity(quantity)

        # Defect: Checks global set of keys and raises conflict across tenants in Treatment!
        if v_key in self._all_keys and (v_tenant, v_key) not in self._idempotency:
            raise IdempotencyConflict("Cross-tenant key collision detected in treatment")

        scoped_key = (v_tenant, v_key)
        if scoped_key in self._idempotency:
            record = self._idempotency[scoped_key]
            if record.item_id != v_item or record.quantity != v_qty:
                raise IdempotencyConflict("Payload conflict")
            return record.reservation

        res_id = self._id_factory()
        res = Reservation(res_id, v_tenant, v_item, v_qty)
        self._reservations[res_id] = res
        self._idempotency[scoped_key] = _IdempotencyRecord(v_tenant, v_item, v_qty, res)
        self._all_keys.add(v_key)
        return res

    def get_reservation(self, *, tenant_id: str, reservation_id: str) -> Reservation | None:
        v_tenant = _validate_str(tenant_id, "tenant_id")
        v_res_id = _validate_str(reservation_id, "reservation_id")
        res = self._reservations.get(v_res_id)
        if res is None or res.tenant_id != v_tenant:
            return None
        return res

