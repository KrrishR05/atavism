"""Tests for event schema and field validation (Task T05 Common Category 2)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from atavism_projection.projector import AccountProjector
from atavism_projection.types import (
    AccountEvent,
    EventType,
    EventValidationError,
)


@pytest.mark.parametrize("bad_account_id", ["", "   ", None, 123, 45.6, True])
def test_validation_rejects_invalid_account_id(projector: AccountProjector, bad_account_id):
    ev = AccountEvent(
        account_id=bad_account_id,  # type: ignore[arg-type]
        event_type=EventType.ACCOUNT_OPENED,
        sequence_id=1,
        amount=Decimal("10.00"),
    )
    with pytest.raises(EventValidationError):
        projector.apply_event(ev)


@pytest.mark.parametrize("bad_sequence_id", [0, -1, -99, True, False, "1", 1.5, None])
def test_validation_rejects_invalid_sequence_id(projector: AccountProjector, bad_sequence_id):
    ev = AccountEvent(
        account_id="ACC-VAL",
        event_type=EventType.ACCOUNT_OPENED,
        sequence_id=bad_sequence_id,  # type: ignore[arg-type]
        amount=Decimal("10.00"),
    )
    with pytest.raises(EventValidationError):
        projector.apply_event(ev)


def test_validation_rejects_invalid_event_type(projector: AccountProjector):
    ev = AccountEvent(
        account_id="ACC-VAL",
        event_type="INVALID_TYPE",  # type: ignore[arg-type]
        sequence_id=1,
        amount=Decimal("10.00"),
    )
    with pytest.raises(EventValidationError):
        projector.apply_event(ev)


@pytest.mark.parametrize("event_type", [EventType.FUNDS_DEPOSITED, EventType.FUNDS_WITHDRAWN])
def test_validation_monetary_rejects_non_none_reason(projector: AccountProjector, opened_account, make_event, event_type):
    acc_id, _ = opened_account
    ev = make_event(acc_id, event_type, 2, amount=Decimal("10.00"), reason="illegal reason")
    with pytest.raises(EventValidationError):
        projector.apply_event(ev)


@pytest.mark.parametrize("event_type", [EventType.FUNDS_DEPOSITED, EventType.FUNDS_WITHDRAWN])
@pytest.mark.parametrize("bad_amount", [Decimal("0.00"), Decimal("-5.00"), None, True, False, "10.00", 10.0])
def test_validation_monetary_rejects_invalid_amount(projector: AccountProjector, opened_account, event_type, bad_amount):
    acc_id, _ = opened_account
    ev = AccountEvent(
        account_id=acc_id,
        event_type=event_type,
        sequence_id=2,
        amount=bad_amount,  # type: ignore[arg-type]
        reason=None,
    )
    with pytest.raises(EventValidationError):
        projector.apply_event(ev)


def test_validation_freeze_rejects_non_none_amount(projector: AccountProjector, opened_account, make_event):
    acc_id, _ = opened_account
    ev = make_event(acc_id, EventType.ACCOUNT_FROZEN, 2, amount=Decimal("10.00"), reason="Security block")
    with pytest.raises(EventValidationError):
        projector.apply_event(ev)


@pytest.mark.parametrize("bad_reason", ["", "   ", "\t\n", None, 123, False])
def test_validation_freeze_rejects_invalid_reason(projector: AccountProjector, opened_account, bad_reason):
    acc_id, _ = opened_account
    ev = AccountEvent(
        account_id=acc_id,
        event_type=EventType.ACCOUNT_FROZEN,
        sequence_id=2,
        amount=None,
        reason=bad_reason,  # type: ignore[arg-type]
    )
    with pytest.raises(EventValidationError):
        projector.apply_event(ev)

