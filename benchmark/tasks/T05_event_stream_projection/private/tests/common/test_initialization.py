"""Tests for account initialization requirements (Task T05 Common Category 1)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from atavism_projection.projector import AccountProjector
from atavism_projection.types import (
    AccountAlreadyOpenedError,
    AccountNotOpenedError,
    EventType,
    EventValidationError,
)


def test_initialization_successful_with_positive_balance(projector: AccountProjector, make_event):
    ev = make_event("ACC-TEST", EventType.ACCOUNT_OPENED, 1, Decimal("250.75"))
    proj = projector.apply_event(ev)

    assert proj.account_id == "ACC-TEST"
    assert proj.balance == Decimal("250.75")
    assert proj.is_frozen is False
    assert proj.last_applied_sequence == 1
    assert proj.pending_buffer_count == 0
    assert proj.is_blocked is False
    assert proj.blocked_sequence_id is None

    fetched = projector.get_projection("ACC-TEST")
    assert fetched == proj


def test_initialization_successful_with_zero_balance(projector: AccountProjector, make_event):
    ev = make_event("ACC-ZERO", EventType.ACCOUNT_OPENED, 1, Decimal("0.00"))
    proj = projector.apply_event(ev)

    assert proj.account_id == "ACC-ZERO"
    assert proj.balance == Decimal("0.00")
    assert proj.is_frozen is False
    assert proj.last_applied_sequence == 1
    assert proj.pending_buffer_count == 0
    assert proj.is_blocked is False
    assert proj.blocked_sequence_id is None


def test_initialization_rejects_non_sequence_one(projector: AccountProjector, make_event):
    ev = make_event("ACC-INVALID", EventType.ACCOUNT_OPENED, 2, Decimal("100.00"))
    with pytest.raises(EventValidationError):
        projector.apply_event(ev)


def test_initialization_rejects_negative_amount(projector: AccountProjector, make_event):
    ev = make_event("ACC-NEG", EventType.ACCOUNT_OPENED, 1, Decimal("-10.00"))
    with pytest.raises(EventValidationError):
        projector.apply_event(ev)


def test_initialization_rejects_non_none_reason(projector: AccountProjector, make_event):
    ev = make_event("ACC-REASON", EventType.ACCOUNT_OPENED, 1, Decimal("100.00"), reason="Opening bonus")
    with pytest.raises(EventValidationError):
        projector.apply_event(ev)


@pytest.mark.parametrize("event_type,amount,reason", [
    (EventType.FUNDS_DEPOSITED, Decimal("50.00"), None),
    (EventType.FUNDS_WITHDRAWN, Decimal("20.00"), None),
    (EventType.ACCOUNT_FROZEN, None, "Suspected fraud"),
])
def test_initialization_rejects_unopened_account(projector: AccountProjector, make_event, event_type, amount, reason):
    ev = make_event("ACC-UNOPENED", event_type, 1, amount=amount, reason=reason)
    with pytest.raises(AccountNotOpenedError):
        projector.apply_event(ev)


def test_initialization_rejects_reopening(projector: AccountProjector, make_event, opened_account):
    acc_id, _ = opened_account
    # Attempting to open again with a new sequence ID
    reopen_ev = make_event(acc_id, EventType.ACCOUNT_OPENED, 1, Decimal("200.00"))  # conflicting payload
    with pytest.raises(Exception):
        projector.apply_event(reopen_ev)


def test_initialization_get_projection_nonexistent(projector: AccountProjector):
    assert projector.get_projection("DOES-NOT-EXIST") is None

