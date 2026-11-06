"""Tests for frozen account invariants and monetary operation rejection (Task T05 Common Category 6)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from atavism_projection.projector import AccountProjector
from atavism_projection.types import (
    AccountFrozenError,
    EventType,
)


def test_frozen_invariants_freeze_success(projector: AccountProjector, opened_account, make_event):
    acc_id, _ = opened_account
    freeze_ev = make_event(acc_id, EventType.ACCOUNT_FROZEN, 2, reason="AML investigation")
    proj = projector.apply_event(freeze_ev)

    assert proj.is_frozen is True
    assert proj.last_applied_sequence == 2
    assert proj.balance == Decimal("100.00")
    assert proj.is_blocked is False
    assert proj.blocked_sequence_id is None


def test_frozen_invariants_duplicate_freeze_idempotent(projector: AccountProjector, opened_account, make_event):
    acc_id, _ = opened_account
    freeze_ev = make_event(acc_id, EventType.ACCOUNT_FROZEN, 2, reason="AML investigation")
    p1 = projector.apply_event(freeze_ev)

    # Identical redelivery
    p2 = projector.apply_event(freeze_ev)
    assert p2 == p1
    assert p2.is_frozen is True
    assert p2.last_applied_sequence == 2


def test_frozen_invariants_deposit_rejected_when_frozen(projector: AccountProjector, opened_account, make_event):
    acc_id, _ = opened_account
    projector.apply_event(make_event(acc_id, EventType.ACCOUNT_FROZEN, 2, reason="Sanctions list match"))

    # Attempt deposit
    dep = make_event(acc_id, EventType.FUNDS_DEPOSITED, 3, Decimal("50.00"))
    with pytest.raises(AccountFrozenError):
        projector.apply_event(dep)

    proj = projector.get_projection(acc_id)
    assert proj is not None
    assert proj.balance == Decimal("100.00")
    assert proj.is_frozen is True
    assert proj.last_applied_sequence == 2
    assert proj.is_blocked is True
    assert proj.blocked_sequence_id == 3


def test_frozen_invariants_withdrawal_rejected_when_frozen(projector: AccountProjector, opened_account, make_event):
    acc_id, _ = opened_account
    projector.apply_event(make_event(acc_id, EventType.ACCOUNT_FROZEN, 2, reason="Sanctions list match"))

    # Attempt withdrawal
    wdr = make_event(acc_id, EventType.FUNDS_WITHDRAWN, 3, Decimal("10.00"))
    with pytest.raises(AccountFrozenError):
        projector.apply_event(wdr)

    proj = projector.get_projection(acc_id)
    assert proj is not None
    assert proj.balance == Decimal("100.00")
    assert proj.is_frozen is True
    assert proj.last_applied_sequence == 2
    assert proj.is_blocked is True
    assert proj.blocked_sequence_id == 3

