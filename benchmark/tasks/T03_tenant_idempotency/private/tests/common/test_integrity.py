"""Category D: State integrity tests for ReservationService."""

from __future__ import annotations

import pytest
from atavism_reservation.service import ReservationService
from atavism_reservation.types import IdempotencyConflict
from conftest import DeterministicIdFactory


class TestStateIntegrity:
    """Verify that failed, invalid, and replayed operations preserve state integrity."""

    def test_conflict_leaves_stored_state_unchanged(self) -> None:
        factory = DeterministicIdFactory()
        service = ReservationService(factory)
        r1 = service.create_reservation(
            tenant_id="tenant-1",
            item_id="item-A",
            quantity=2,
            idempotency_key="key-1",
        )

        # Trigger conflict
        with pytest.raises(IdempotencyConflict):
            service.create_reservation(
                tenant_id="tenant-1",
                item_id="item-DIFFERENT",
                quantity=2,
                idempotency_key="key-1",
            )

        # Stored reservation must be untouched
        retrieved = service.get_reservation(tenant_id="tenant-1", reservation_id=r1.reservation_id)
        assert retrieved == r1
        assert factory.counter == 1

        # Subsequent exact replay of original payload still succeeds
        replayed = service.create_reservation(
            tenant_id="tenant-1",
            item_id="item-A",
            quantity=2,
            idempotency_key="key-1",
        )
        assert replayed == r1
        assert factory.counter == 1

    def test_invalid_request_does_not_register_key(self) -> None:
        factory = DeterministicIdFactory()
        service = ReservationService(factory)

        # Invalid request with key-1
        with pytest.raises(ValueError):
            service.create_reservation(
                tenant_id="",
                item_id="item-A",
                quantity=2,
                idempotency_key="key-1",
            )
        assert factory.counter == 0

        # Now send valid request with key-1: must succeed as a new creation
        r = service.create_reservation(
            tenant_id="tenant-1",
            item_id="item-A",
            quantity=2,
            idempotency_key="key-1",
        )
        assert r.reservation_id == "res-0001"
        assert factory.counter == 1

    def test_factory_error_propagates_and_preserves_clean_state(self) -> None:
        call_count = 0

        def failing_factory() -> str:
            nonlocal call_count
            call_count += 1
            raise RuntimeError("Database or ID generator failure")

        service = ReservationService(failing_factory)
        with pytest.raises(RuntimeError, match="ID generator failure"):
            service.create_reservation(
                tenant_id="tenant-1",
                item_id="item-A",
                quantity=2,
                idempotency_key="key-1",
            )

        assert call_count == 1
        # No reservation should have been registered under key-1
        # If we now swap in a working factory, it should create cleanly
        service._id_factory = lambda: "res-recovered"  # type: ignore[assignment]
        r = service.create_reservation(
            tenant_id="tenant-1",
            item_id="item-A",
            quantity=2,
            idempotency_key="key-1",
        )
        assert r.reservation_id == "res-recovered"

    def test_failed_requests_do_not_consume_identifiers(self) -> None:
        factory = DeterministicIdFactory()
        service = ReservationService(factory)

        for _ in range(5):
            with pytest.raises(ValueError):
                service.create_reservation(
                    tenant_id="tenant-1",
                    item_id="item-A",
                    quantity=-1,
                    idempotency_key="bad-key",
                )

        assert factory.counter == 0

        # First valid request gets res-0001
        res = service.create_reservation(
            tenant_id="tenant-1",
            item_id="item-A",
            quantity=1,
            idempotency_key="first-valid",
        )
        assert res.reservation_id == "res-0001"
        assert factory.counter == 1

