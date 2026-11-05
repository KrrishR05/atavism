"""Category C: Tenant isolation tests for ReservationService."""

from __future__ import annotations

from atavism_reservation.service import ReservationService
from conftest import DeterministicIdFactory


class TestTenantIsolation:
    """Verify tenant isolation during reservation retrieval."""

    def test_tenant_retrieves_own_reservation(self) -> None:
        factory = DeterministicIdFactory()
        service = ReservationService(factory)
        created = service.create_reservation(
            tenant_id="tenant-1",
            item_id="item-A",
            quantity=3,
            idempotency_key="k1",
        )
        retrieved = service.get_reservation(
            tenant_id="tenant-1",
            reservation_id=created.reservation_id,
        )
        assert retrieved is not None
        assert retrieved == created

    def test_tenant_cannot_retrieve_another_tenants_reservation(self) -> None:
        """Querying a reservation ID belonging to a different tenant must return None."""
        factory = DeterministicIdFactory()
        service = ReservationService(factory)
        res_tenant1 = service.create_reservation(
            tenant_id="tenant-1",
            item_id="item-A",
            quantity=3,
            idempotency_key="k1",
        )

        # Tenant 2 attempts to retrieve Tenant 1's reservation
        retrieved_by_tenant2 = service.get_reservation(
            tenant_id="tenant-2",
            reservation_id=res_tenant1.reservation_id,
        )
        assert retrieved_by_tenant2 is None

    def test_unknown_reservation_id_returns_none(self) -> None:
        factory = DeterministicIdFactory()
        service = ReservationService(factory)
        assert service.get_reservation(tenant_id="tenant-1", reservation_id="non-existent-res") is None

    def test_multiple_reservations_per_tenant_retrieved_independently(self) -> None:
        factory = DeterministicIdFactory()
        service = ReservationService(factory)
        r1 = service.create_reservation(tenant_id="tenant-1", item_id="item-A", quantity=1, idempotency_key="k1")
        r2 = service.create_reservation(tenant_id="tenant-1", item_id="item-B", quantity=2, idempotency_key="k2")

        assert service.get_reservation(tenant_id="tenant-1", reservation_id=r1.reservation_id) == r1
        assert service.get_reservation(tenant_id="tenant-1", reservation_id=r2.reservation_id) == r2

    def test_same_item_reservations_partitioned_by_tenant(self) -> None:
        factory = DeterministicIdFactory()
        service = ReservationService(factory)
        r1 = service.create_reservation(tenant_id="tenant-1", item_id="shared-item", quantity=5, idempotency_key="k1")
        r2 = service.create_reservation(tenant_id="tenant-2", item_id="shared-item", quantity=10, idempotency_key="k2")

        # Tenant 1 can only retrieve r1
        assert service.get_reservation(tenant_id="tenant-1", reservation_id=r1.reservation_id) == r1
        assert service.get_reservation(tenant_id="tenant-1", reservation_id=r2.reservation_id) is None

        # Tenant 2 can only retrieve r2
        assert service.get_reservation(tenant_id="tenant-2", reservation_id=r2.reservation_id) == r2
        assert service.get_reservation(tenant_id="tenant-2", reservation_id=r1.reservation_id) is None

