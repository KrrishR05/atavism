"""Tests for monetary precision and Decimal invariants (Task T05 Common Category 3)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from atavism_projection.projector import AccountProjector
from atavism_projection.types import (
    AccountEvent,
    EventType,
    EventValidationError,
)


@pytest.mark.parametrize("non_finite_str", ["NaN", "-NaN", "Infinity", "-Infinity", "sNaN"])
def test_precision_rejects_non_finite_decimals(projector: AccountProjector, non_finite_str):
    val = Decimal(non_finite_str)
    ev = AccountEvent(
        account_id="ACC-PREC",
        event_type=EventType.ACCOUNT_OPENED,
        sequence_id=1,
        amount=val,
    )
    with pytest.raises(EventValidationError):
        projector.apply_event(ev)


@pytest.mark.parametrize("excess_precision", [
    Decimal("10.125"),
    Decimal("10.001"),
    Decimal("10.000"),
    Decimal("0.0001"),
])
def test_precision_rejects_more_than_two_decimal_places(projector: AccountProjector, excess_precision):
    ev = AccountEvent(
        account_id="ACC-PREC",
        event_type=EventType.ACCOUNT_OPENED,
        sequence_id=1,
        amount=excess_precision,
    )
    with pytest.raises(EventValidationError):
        projector.apply_event(ev)


@pytest.mark.parametrize("valid_amount", [
    Decimal("100"),
    Decimal("100.5"),
    Decimal("100.55"),
    Decimal("0"),
    Decimal("0.0"),
    Decimal("0.00"),
])
def test_precision_accepts_valid_decimal_places(projector: AccountProjector, valid_amount):
    ev = AccountEvent(
        account_id=f"ACC-OK-{valid_amount}",
        event_type=EventType.ACCOUNT_OPENED,
        sequence_id=1,
        amount=valid_amount,
    )
    proj = projector.apply_event(ev)
    assert proj.balance == valid_amount
    assert isinstance(proj.balance, Decimal)


def test_precision_arithmetic_exactness(projector: AccountProjector, opened_account, make_event):
    acc_id, _ = opened_account
    # 100.00 + 0.10 + 0.20 = 100.30 (float would produce 100.30000000000001)
    dep1 = make_event(acc_id, EventType.FUNDS_DEPOSITED, 2, Decimal("0.10"))
    dep2 = make_event(acc_id, EventType.FUNDS_DEPOSITED, 3, Decimal("0.20"))

    p1 = projector.apply_event(dep1)
    assert p1.balance == Decimal("100.10")

    p2 = projector.apply_event(dep2)
    assert p2.balance == Decimal("100.30")
    assert str(p2.balance) == "100.30"

