"""Treatment-specific tests for T03 Variant B (Tenant-Scoped Idempotency Namespace).

In Variant B, an idempotency key is unique only within the context of the requesting tenant.
Different tenants may independently use identical idempotency keys without conflicting.
"""

from __future__ import annotations

import pytest
from atavism_reservation.service import ReservationService
from atavism_reservation.types import IdempotencyConflict, Reservation
from conftest import DeterministicIdFactory


class TestTreatmentCrossTenantScope:
    """Verify tenant-scoped idempotency key independence across different tenants."""

    def test_same_key_across_different_tenants_creates_independent_reservations(self) -> None:
        """Tenant B may use the exact same key as Tenant A and receive an independent reservation."""
        factory = DeterministicIdFactory()
        service = ReservationService(factory)

        res_a = service.create_reservation(
            tenant_id="tenant-A",
            item_id="item-widget",
            quantity=2,
            idempotency_key="reused-key-1",
        )
        assert res_a.tenant_id == "tenant-A"
        assert res_a.reservation_id == "res-0001"
        assert factory.counter == 1

        # Tenant B uses the identical key
        res_b = service.create_reservation(
            tenant_id="tenant-B",
            item_id="item-widget",
            quantity=2,
            idempotency_key="reused-key-1",
        )
        assert res_b.tenant_id == "tenant-B"
        assert res_b.reservation_id == "res-0002"
        assert factory.counter == 2
        assert res_a.reservation_id != res_b.reservation_id

    def test_each_tenant_replays_own_request_independently(self) -> None:
        """Replaying reused-key-1 under Tenant A returns res_a; under Tenant B returns res_b."""
        factory = DeterministicIdFactory()
        service = ReservationService(factory)

        res_a = service.create_reservation(
            tenant_id="tenant-A",
            item_id="item-widget",
            quantity=2,
            idempotency_key="reused-key-1",
        )
        res_b = service.create_reservation(
            tenant_id="tenant-B",
            item_id="item-widget",
            quantity=5,
            idempotency_key="reused-key-1",
        )
        assert factory.counter == 2

        # Replay Tenant A
        replay_a = service.create_reservation(
            tenant_id="tenant-A",
            item_id="item-widget",
            quantity=2,
            idempotency_key="reused-key-1",
        )
        assert replay_a == res_a
        assert factory.counter == 2

        # Replay Tenant B
        replay_b = service.create_reservation(
            tenant_id="tenant-B",
            item_id="item-widget",
            quantity=5,
            idempotency_key="reused-key-1",
        )
        assert replay_b == res_b
        assert factory.counter == 2

    def test_payload_conflict_in_one_tenant_does_not_affect_other_tenant(self) -> None:
        """A conflict in Tenant A using reused-key-1 does not block Tenant B from creating or replaying."""
        factory = DeterministicIdFactory()
        service = ReservationService(factory)

        res_a = service.create_reservation(
            tenant_id="tenant-A",
            item_id="item-widget",
            quantity=2,
            idempotency_key="reused-key-1",
        )

        # Tenant A triggers conflict on reused-key-1
        with pytest.raises(IdempotencyConflict):
            service.create_reservation(
                tenant_id="tenant-A",
                item_id="item-widget",
                quantity=999,  # different quantity
                idempotency_key="reused-key-1",
            )

        # Tenant B can still use reused-key-1 without issue
        res_b = service.create_reservation(
            tenant_id="tenant-B",
            item_id="item-widget",
            quantity=10,
            idempotency_key="reused-key-1",
        )
        assert res_b.tenant_id == "tenant-B"
        assert res_b.quantity == 10
        assert factory.counter == 2

    def test_cross_tenant_reservations_with_same_key_remain_isolated_in_get(self) -> None:
        """Tenant A cannot retrieve Tenant B's reservation even when sharing an idempotency key."""
        factory = DeterministicIdFactory()
        service = ReservationService(factory)

        res_a = service.create_reservation(
            tenant_id="tenant-A",
            item_id="item-widget",
            quantity=2,
            idempotency_key="same-key",
        )
        res_b = service.create_reservation(
            tenant_id="tenant-B",
            item_id="item-widget",
            quantity=5,
            idempotency_key="same-key",
        )

        assert service.get_reservation(tenant_id="tenant-A", reservation_id=res_a.reservation_id) == res_a
        assert service.get_reservation(tenant_id="tenant-A", reservation_id=res_b.reservation_id) is None

        assert service.get_reservation(tenant_id="tenant-B", reservation_id=res_b.reservation_id) == res_b
        assert service.get_reservation(tenant_id="tenant-B", reservation_id=res_a.reservation_id) is None

    def test_multiple_tenants_independent_idempotency_partitions(self) -> None:
        """Three distinct tenants can all use the same idempotency key simultaneously."""
        factory = DeterministicIdFactory()
        service = ReservationService(factory)

        r_alpha = service.create_reservation(tenant_id="alpha", item_id="item-1", quantity=1, idempotency_key="universal-key")
        r_beta = service.create_reservation(tenant_id="beta", item_id="item-2", quantity=2, idempotency_key="universal-key")
        r_gamma = service.create_reservation(tenant_id="gamma", item_id="item-3", quantity=3, idempotency_key="universal-key")

        assert len({r_alpha.reservation_id, r_beta.reservation_id, r_gamma.reservation_id}) == 3
        assert factory.counter == 3

    def test_same_tenant_different_payload_conflicts_normally_in_treatment(self) -> None:
        """Treatment variant still enforces strict payload conflict within the same tenant."""
        factory = DeterministicIdFactory()
        service = ReservationService(factory)

        service.create_reservation(tenant_id="tenant-A", item_id="item-1", quantity=1, idempotency_key="k1")
        with pytest.raises(IdempotencyConflict):
            service.create_reservation(tenant_id="tenant-A", item_id="item-1", quantity=2, idempotency_key="k1")

