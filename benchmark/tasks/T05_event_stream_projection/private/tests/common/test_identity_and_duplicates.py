"""Tests for event identity and duplicate payload handling (Task T05 Common Category 4)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from atavism_projection.projector import AccountProjector
from atavism_projection.types import (
    ConflictingEventError,
    EventType,
)


def test_identity_identical_duplicate_applied_ignored_idempotently(projector: AccountProjector, opened_account, make_event):
    acc_id, proj_open = opened_account
    dep = make_event(acc_id, EventType.FUNDS_DEPOSITED, 2, Decimal("50.00"))
    p1 = projector.apply_event(dep)
    assert p1.balance == Decimal("150.00")
    assert p1.last_applied_sequence == 2

    # Redeliver identical sequence 2
    p2 = projector.apply_event(dep)
    assert p2.balance == Decimal("150.00")
    assert p2.last_applied_sequence == 2
    assert p2 == p1


def test_identity_conflicting_duplicate_applied_raises_conflict(projector: AccountProjector, opened_account, make_event):
    acc_id, _ = opened_account
    dep = make_event(acc_id, EventType.FUNDS_DEPOSITED, 2, Decimal("50.00"))
    projector.apply_event(dep)

    # Redeliver sequence 2 with conflicting amount
    conflicting_dep = make_event(acc_id, EventType.FUNDS_DEPOSITED, 2, Decimal("75.00"))
    with pytest.raises(ConflictingEventError):
        projector.apply_event(conflicting_dep)

    # State must be untouched
    proj = projector.get_projection(acc_id)
    assert proj is not None
    assert proj.balance == Decimal("150.00")
    assert proj.last_applied_sequence == 2


def test_identity_conflicting_event_type_raises_conflict(projector: AccountProjector, opened_account, make_event):
    acc_id, _ = opened_account
    dep = make_event(acc_id, EventType.FUNDS_DEPOSITED, 2, Decimal("50.00"))
    projector.apply_event(dep)

    # Redeliver sequence 2 with conflicting event type (withdrawal instead of deposit)
    conflicting_type = make_event(acc_id, EventType.FUNDS_WITHDRAWN, 2, Decimal("50.00"))
    with pytest.raises(ConflictingEventError):
        projector.apply_event(conflicting_type)


def test_identity_identical_opening_duplicate_ignored(projector: AccountProjector, make_event):
    ev1 = make_event("ACC-IDEM-OPEN", EventType.ACCOUNT_OPENED, 1, Decimal("100.00"))
    p1 = projector.apply_event(ev1)

    # Redeliver identical sequence 1
    p2 = projector.apply_event(ev1)
    assert p2 == p1
    assert p2.balance == Decimal("100.00")
    assert p2.last_applied_sequence == 1


def test_identity_conflicting_opening_duplicate_raises_conflict(projector: AccountProjector, make_event):
    ev1 = make_event("ACC-IDEM-OPEN2", EventType.ACCOUNT_OPENED, 1, Decimal("100.00"))
    projector.apply_event(ev1)

    # Redeliver sequence 1 with different amount
    ev2 = make_event("ACC-IDEM-OPEN2", EventType.ACCOUNT_OPENED, 1, Decimal("200.00"))
    with pytest.raises(ConflictingEventError):
        projector.apply_event(ev2)

