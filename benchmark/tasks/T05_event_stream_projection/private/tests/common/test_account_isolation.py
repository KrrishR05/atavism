"""Tests for cross-account isolation and state partitioning (Task T05 Common Category 7)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from atavism_projection.projector import AccountProjector
from atavism_projection.types import (
    AccountFrozenError,
    EventType,
    InsufficientFundsError,
)


def test_account_isolation_interleaved_operations(projector: AccountProjector, make_event):
    # Open 3 accounts
    p1 = projector.apply_event(make_event("ACC-A", EventType.ACCOUNT_OPENED, 1, Decimal("100.00")))
    p2 = projector.apply_event(make_event("ACC-B", EventType.ACCOUNT_OPENED, 1, Decimal("200.00")))
    p3 = projector.apply_event(make_event("ACC-C", EventType.ACCOUNT_OPENED, 1, Decimal("300.00")))

    # Interleaved mutations
    projector.apply_event(make_event("ACC-A", EventType.FUNDS_DEPOSITED, 2, Decimal("50.00")))
    projector.apply_event(make_event("ACC-B", EventType.FUNDS_WITHDRAWN, 2, Decimal("50.00")))
    projector.apply_event(make_event("ACC-C", EventType.ACCOUNT_FROZEN, 2, reason="Risk hold"))

    projector.apply_event(make_event("ACC-A", EventType.FUNDS_WITHDRAWN, 3, Decimal("25.00")))
    projector.apply_event(make_event("ACC-B", EventType.FUNDS_DEPOSITED, 3, Decimal("100.00")))

    proj_a = projector.get_projection("ACC-A")
    proj_b = projector.get_projection("ACC-B")
    proj_c = projector.get_projection("ACC-C")

    assert proj_a is not None and proj_a.balance == Decimal("125.00") and proj_a.last_applied_sequence == 3
    assert proj_b is not None and proj_b.balance == Decimal("250.00") and proj_b.last_applied_sequence == 3
    assert proj_c is not None and proj_c.balance == Decimal("300.00") and proj_c.is_frozen is True


def test_account_isolation_failure_does_not_leak(projector: AccountProjector, make_event):
    projector.apply_event(make_event("ACC-GOOD", EventType.ACCOUNT_OPENED, 1, Decimal("100.00")))
    projector.apply_event(make_event("ACC-FAIL", EventType.ACCOUNT_OPENED, 1, Decimal("10.00")))

    # ACC-FAIL fails overdraft
    with pytest.raises(InsufficientFundsError):
        projector.apply_event(make_event("ACC-FAIL", EventType.FUNDS_WITHDRAWN, 2, Decimal("50.00")))

    # ACC-GOOD proceeds unaffected
    proj_good = projector.apply_event(make_event("ACC-GOOD", EventType.FUNDS_DEPOSITED, 2, Decimal("20.00")))
    assert proj_good.balance == Decimal("120.00")
    assert proj_good.is_blocked is False

    proj_fail = projector.get_projection("ACC-FAIL")
    assert proj_fail is not None
    assert proj_fail.is_blocked is True
    assert proj_fail.blocked_sequence_id == 2

