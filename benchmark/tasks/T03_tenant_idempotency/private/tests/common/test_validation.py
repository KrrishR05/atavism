"""Category A: Input validation tests for ReservationService."""

from __future__ import annotations

import pytest
from atavism_reservation.service import ReservationService
from conftest import DeterministicIdFactory


class TestValidation:
    """Verify input validation across all parameters and methods."""

    @pytest.mark.parametrize("bad_tenant", ["", "   ", "\t", "\n", None, 123, []])
    def test_invalid_tenant_id_raises_value_error(self, bad_tenant: object) -> None:
        factory = DeterministicIdFactory()
        service = ReservationService(factory)
        with pytest.raises(ValueError):
            service.create_reservation(
                tenant_id=bad_tenant,  # type: ignore[arg-type]
                item_id="item-1",
                quantity=1,
                idempotency_key="key-1",
            )
        assert factory.counter == 0

    @pytest.mark.parametrize("bad_item", ["", "   ", "\t", "\n", None, 456, {}])
    def test_invalid_item_id_raises_value_error(self, bad_item: object) -> None:
        factory = DeterministicIdFactory()
        service = ReservationService(factory)
        with pytest.raises(ValueError):
            service.create_reservation(
                tenant_id="tenant-1",
                item_id=bad_item,  # type: ignore[arg-type]
                quantity=1,
                idempotency_key="key-1",
            )
        assert factory.counter == 0

    @pytest.mark.parametrize("bad_key", ["", "   ", "\t", "\n", None, 789, ()])
    def test_invalid_idempotency_key_raises_value_error(self, bad_key: object) -> None:
        factory = DeterministicIdFactory()
        service = ReservationService(factory)
        with pytest.raises(ValueError):
            service.create_reservation(
                tenant_id="tenant-1",
                item_id="item-1",
                quantity=1,
                idempotency_key=bad_key,  # type: ignore[arg-type]
            )
        assert factory.counter == 0

    @pytest.mark.parametrize("bad_qty", [0, -1, -100, 1.5, 0.0, "5", None, [1]])
    def test_non_positive_or_non_integer_quantity_raises_value_error(self, bad_qty: object) -> None:
        factory = DeterministicIdFactory()
        service = ReservationService(factory)
        with pytest.raises(ValueError):
            service.create_reservation(
                tenant_id="tenant-1",
                item_id="item-1",
                quantity=bad_qty,  # type: ignore[arg-type]
                idempotency_key="key-1",
            )
        assert factory.counter == 0

    def test_boolean_true_quantity_rejected(self) -> None:
        """Python bool subclasses int; True must be explicitly rejected as quantity."""
        factory = DeterministicIdFactory()
        service = ReservationService(factory)
        with pytest.raises(ValueError):
            service.create_reservation(
                tenant_id="tenant-1",
                item_id="item-1",
                quantity=True,  # type: ignore[arg-type]
                idempotency_key="key-1",
            )
        assert factory.counter == 0

    def test_boolean_false_quantity_rejected(self) -> None:
        factory = DeterministicIdFactory()
        service = ReservationService(factory)
        with pytest.raises(ValueError):
            service.create_reservation(
                tenant_id="tenant-1",
                item_id="item-1",
                quantity=False,  # type: ignore[arg-type]
                idempotency_key="key-1",
            )
        assert factory.counter == 0

    def test_validation_precedes_idempotency_lookup(self) -> None:
        """An invalid request replaying an existing key must raise ValueError, not return existing reservation."""
        factory = DeterministicIdFactory()
        service = ReservationService(factory)
        res = service.create_reservation(
            tenant_id="tenant-1",
            item_id="item-1",
            quantity=5,
            idempotency_key="key-1",
        )
        assert res.quantity == 5
        assert factory.counter == 1

        # Replay with same key but invalid quantity=0 must fail with ValueError
        with pytest.raises(ValueError):
            service.create_reservation(
                tenant_id="tenant-1",
                item_id="item-1",
                quantity=0,
                idempotency_key="key-1",
            )

        # Replay with same key but invalid quantity=True must fail with ValueError
        with pytest.raises(ValueError):
            service.create_reservation(
                tenant_id="tenant-1",
                item_id="item-1",
                quantity=True,  # type: ignore[arg-type]
                idempotency_key="key-1",
            )

        # Factory should not have been called again
        assert factory.counter == 1

    @pytest.mark.parametrize("bad_tenant", ["", "   ", None, 123])
    def test_get_reservation_invalid_tenant_raises_value_error(self, bad_tenant: object) -> None:
        factory = DeterministicIdFactory()
        service = ReservationService(factory)
        with pytest.raises(ValueError):
            service.get_reservation(
                tenant_id=bad_tenant,  # type: ignore[arg-type]
                reservation_id="res-0001",
            )

    @pytest.mark.parametrize("bad_res_id", ["", "   ", None, 456])
    def test_get_reservation_invalid_reservation_id_raises_value_error(self, bad_res_id: object) -> None:
        factory = DeterministicIdFactory()
        service = ReservationService(factory)
        with pytest.raises(ValueError):
            service.get_reservation(
                tenant_id="tenant-1",
                reservation_id=bad_res_id,  # type: ignore[arg-type]
            )

    def test_original_string_values_preserved_without_trimming(self) -> None:
        """Strings with leading/trailing spaces must be preserved as distinct values, not trimmed."""
        factory = DeterministicIdFactory()
        service = ReservationService(factory)
        res1 = service.create_reservation(
            tenant_id="tenant-1",
            item_id=" item-with-spaces ",
            quantity=2,
            idempotency_key=" key-1 ",
        )
        assert res1.item_id == " item-with-spaces "

        # Different key without spaces must create a new reservation
        res2 = service.create_reservation(
            tenant_id="tenant-1",
            item_id=" item-with-spaces ",
            quantity=2,
            idempotency_key="key-1",
        )
        assert res2.reservation_id != res1.reservation_id
        assert factory.counter == 2

