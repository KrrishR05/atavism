"""Type definitions and domain objects for the reservation service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Reservation:
    """An immutable reservation record."""

    reservation_id: str
    tenant_id: str
    item_id: str
    quantity: int


class IdempotencyConflict(Exception):
    """Raised when an idempotency key is reused with conflicting parameters or across unauthorized scopes."""

    pass

