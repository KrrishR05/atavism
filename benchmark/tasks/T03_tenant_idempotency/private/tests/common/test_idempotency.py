"""Category B: Same-tenant idempotency and replay tests for ReservationService."""

from __future__ import annotations

import pytest
from atavism_reservation.service import ReservationService
from atavism_reservation.types import IdempotencyConflict, Reservation
from conftest import DeterministicIdFactory


class TestSameTenantIdempotency:
    """Verify basic idempotency and conflict detection within a single tenant."""

    def test_first_request_creates_reservation(self) -> None:
        factory = DeterministicIdFactory()
        service = ReservationService(factory)
        res = service.create_reservation(
            tenant_id="tenant-alpha",
            item_id="item-widget-1",
            quantity=10,
            idempotency_key="idemp-key-100",
        )
        assert isinstance(res, Reservation)
        assert res.reservation_id == "res-0001"
        assert res.tenant_id == "tenant-alpha"
        assert res.item_id == "item-widget-1"
        assert res.quantity == 10
        assert factory.counter == 1

    def test_exact_replay_returns_original_reservation(self) -> None:
        factory = DeterministicIdFactory()
        service = ReservationService(factory)
        res1 = service.create_reservation(
            tenant_id="tenant-alpha",
            item_id="item-widget-1",
            quantity=10,
            idempotency_key="idemp-key-100",
        )
        res2 = service.create_reservation(
            tenant_id="tenant-alpha",
            item_id="item-widget-1",
            quantity=10,
            idempotency_key="idemp-key-100",
        )
        assert res1 == res2
        assert res1.reservation_id == res2.reservation_id
        assert factory.counter == 1

    def test_replay_does_not_consume_new_identifier(self) -> None:
        factory = DeterministicIdFactory()
        service = ReservationService(factory)
        service.create_reservation(
            tenant_id="tenant-alpha",
            item_id="item-widget-1",
            quantity=10,
            idempotency_key="idemp-key-100",
        )
        assert factory.counter == 1

        for _ in range(5):
            service.create_reservation(
                tenant_id="tenant-alpha",
                item_id="item-widget-1",
                quantity=10,
                idempotency_key="idemp-key-100",
            )
            assert factory.counter == 1

    def test_replay_with_different_item_id_raises_conflict(self) -> None:
        factory = DeterministicIdFactory()
        service = ReservationService(factory)
        service.create_reservation(
            tenant_id="tenant-alpha",
            item_id="item-widget-1",
            quantity=10,
            idempotency_key="idemp-key-100",
        )
        with pytest.raises(IdempotencyConflict):
            service.create_reservation(
                tenant_id="tenant-alpha",
                item_id="item-widget-DIFFERENT",
                quantity=10,
                idempotency_key="idemp-key-100",
            )
        assert factory.counter == 1

    def test_replay_with_different_quantity_raises_conflict(self) -> None:
        factory = DeterministicIdFactory()
        service = ReservationService(factory)
        service.create_reservation(
            tenant_id="tenant-alpha",
            item_id="item-widget-1",
            quantity=10,
            idempotency_key="idemp-key-100",
        )
        with pytest.raises(IdempotencyConflict):
            service.create_reservation(
                tenant_id="tenant-alpha",
                item_id="item-widget-1",
                quantity=999,
                idempotency_key="idemp-key-100",
            )
        assert factory.counter == 1

    def test_distinct_keys_within_same_tenant_create_distinct_reservations(self) -> None:
        factory = DeterministicIdFactory()
        service = ReservationService(factory)
        res1 = service.create_reservation(
            tenant_id="tenant-alpha",
            item_id="item-widget-1",
            quantity=10,
            idempotency_key="key-A",
        )
        res2 = service.create_reservation(
            tenant_id="tenant-alpha",
            item_id="item-widget-1",
            quantity=10,
            idempotency_key="key-B",
        )
        assert res1.reservation_id != res2.reservation_id
        assert factory.counter == 2

