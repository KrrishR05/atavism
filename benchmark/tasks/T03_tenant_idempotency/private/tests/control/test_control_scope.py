"""Control-specific tests for T03 Variant A (Global Idempotency Namespace).

In Variant A, an idempotency key is unique across the entire service.
Cross-tenant reuse of an idempotency key must be rejected with IdempotencyConflict.
"""

from __future__ import annotations

import pytest
from atavism_reservation.service import ReservationService
from atavism_reservation.types import IdempotencyConflict
from conftest import DeterministicIdFactory


class TestControlCrossTenantScope:
    """Verify global idempotency key collision behavior across different tenants."""

    def test_cross_tenant_key_reuse_same_payload_raises_conflict(self) -> None:
        """Tenant B using key previously used by Tenant A (even with identical payload) must raise IdempotencyConflict."""
        factory = DeterministicIdFactory()
        service = ReservationService(factory)

        res_a = service.create_reservation(
            tenant_id="tenant-A",
            item_id="item-100",
            quantity=5,
            idempotency_key="shared-key-1",
        )
        assert res_a.tenant_id == "tenant-A"
        assert factory.counter == 1

        # Tenant B attempts to use the same key
        with pytest.raises(IdempotencyConflict):
            service.create_reservation(
                tenant_id="tenant-B",
                item_id="item-100",
                quantity=5,
                idempotency_key="shared-key-1",
            )

        # Must not have allocated an identifier for Tenant B
        assert factory.counter == 1

    def test_cross_tenant_key_reuse_different_payload_raises_conflict(self) -> None:
        """Tenant B using key with a different payload also raises IdempotencyConflict."""
        factory = DeterministicIdFactory()
        service = ReservationService(factory)

        service.create_reservation(
            tenant_id="tenant-A",
            item_id="item-100",
            quantity=5,
            idempotency_key="shared-key-1",
        )
        assert factory.counter == 1

        with pytest.raises(IdempotencyConflict):
            service.create_reservation(
                tenant_id="tenant-B",
                item_id="item-DIFFERENT",
                quantity=20,
                idempotency_key="shared-key-1",
            )
        assert factory.counter == 1

    def test_cross_tenant_collision_does_not_leak_reservation_details(self) -> None:
        """Tenant B must never receive Tenant A's reservation during an idempotency collision."""
        factory = DeterministicIdFactory()
        service = ReservationService(factory)

        res_a = service.create_reservation(
            tenant_id="tenant-A",
            item_id="secret-item",
            quantity=1,
            idempotency_key="secret-key",
        )

        with pytest.raises(IdempotencyConflict) as exc_info:
            service.create_reservation(
                tenant_id="tenant-B",
                item_id="secret-item",
                quantity=1,
                idempotency_key="secret-key",
            )

        # Exception message should not leak reservation id or secret details
        assert res_a.reservation_id not in str(exc_info.value)

    def test_tenant_a_can_still_replay_after_cross_tenant_collision(self) -> None:
        """A collision caused by Tenant B must not damage Tenant A's ability to replay."""
        factory = DeterministicIdFactory()
        service = ReservationService(factory)

        res_a = service.create_reservation(
            tenant_id="tenant-A",
            item_id="item-100",
            quantity=5,
            idempotency_key="shared-key-1",
        )

        # Tenant B triggers collision
        with pytest.raises(IdempotencyConflict):
            service.create_reservation(
                tenant_id="tenant-B",
                item_id="item-100",
                quantity=5,
                idempotency_key="shared-key-1",
            )

        # Tenant A replays key: must succeed and return original reservation
        replayed = service.create_reservation(
            tenant_id="tenant-A",
            item_id="item-100",
            quantity=5,
            idempotency_key="shared-key-1",
        )
        assert replayed == res_a
        assert factory.counter == 1

    def test_cross_tenant_collision_does_not_mutate_stored_reservation(self) -> None:
        factory = DeterministicIdFactory()
        service = ReservationService(factory)

        res_a = service.create_reservation(
            tenant_id="tenant-A",
            item_id="item-100",
            quantity=5,
            idempotency_key="shared-key-1",
        )

        with pytest.raises(IdempotencyConflict):
            service.create_reservation(
                tenant_id="tenant-B",
                item_id="item-200",
                quantity=99,
                idempotency_key="shared-key-1",
            )

        retrieved = service.get_reservation(tenant_id="tenant-A", reservation_id=res_a.reservation_id)
        assert retrieved == res_a
        assert retrieved.quantity == 5
        assert retrieved.item_id == "item-100"

