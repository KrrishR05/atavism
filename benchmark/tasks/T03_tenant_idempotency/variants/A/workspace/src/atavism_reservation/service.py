"""Reservation service implementation stub.

Implement ReservationService according to the specifications in contract.md.
"""

from __future__ import annotations

from typing import Callable

from .types import IdempotencyConflict, Reservation


class ReservationService:
    """A multi-tenant reservation service with idempotency support."""

    def __init__(
        self,
        id_factory: Callable[[], str],
    ) -> None:
        """Initialize the reservation service.

        Args:
            id_factory: Callable supplying unique reservation identifiers for new reservations.
        """
        self._id_factory = id_factory

    def create_reservation(
        self,
        *,
        tenant_id: str,
        item_id: str,
        quantity: int,
        idempotency_key: str,
    ) -> Reservation:
        """Create a reservation or return an existing one for idempotent replay.

        Args:
            tenant_id: Identifier of the tenant making the reservation.
            item_id: Identifier of the item being reserved.
            quantity: Positive integer quantity to reserve.
            idempotency_key: Client-supplied key to prevent duplicate operations.

        Returns:
            The created or replayed Reservation object.

        Raises:
            ValueError: If any input argument is invalid.
            IdempotencyConflict: If the key was used with conflicting parameters or scope.
        """
        raise NotImplementedError("Implement create_reservation")

    def get_reservation(
        self,
        *,
        tenant_id: str,
        reservation_id: str,
    ) -> Reservation | None:
        """Retrieve an existing reservation belonging to the specified tenant.

        Args:
            tenant_id: Identifier of the tenant requesting the reservation.
            reservation_id: Identifier of the reservation to retrieve.

        Returns:
            The Reservation if found and owned by tenant_id; otherwise None.

        Raises:
            ValueError: If tenant_id or reservation_id is invalid.
        """
        raise NotImplementedError("Implement get_reservation")

