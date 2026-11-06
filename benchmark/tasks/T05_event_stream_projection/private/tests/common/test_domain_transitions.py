"""Tests for domain state transitions and balance mutations (Task T05 Common Category 5)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from atavism_projection.projector import AccountProjector
from atavism_projection.types import (
    EventType,
    InsufficientFundsError,
)


def test_domain_deposit_success(projector: AccountProjector, opened_account, make_event):
    acc_id, _ = opened_account
    dep = make_event(acc_id, EventType.FUNDS_DEPOSITED, 2, Decimal("45.50"))
    proj = projector.apply_event(dep)

    assert proj.balance == Decimal("145.50")
    assert proj.last_applied_sequence == 2
    assert proj.is_blocked is False
    assert proj.blocked_sequence_id is None


def test_domain_withdrawal_success(projector: AccountProjector, opened_account, make_event):
    acc_id, _ = opened_account
    wdr = make_event(acc_id, EventType.FUNDS_WITHDRAWN, 2, Decimal("30.00"))
    proj = projector.apply_event(wdr)

    assert proj.balance == Decimal("70.00")
    assert proj.last_applied_sequence == 2
    assert proj.is_blocked is False
    assert proj.blocked_sequence_id is None


def test_domain_withdrawal_to_exact_zero_success(projector: AccountProjector, opened_account, make_event):
    acc_id, _ = opened_account
    wdr = make_event(acc_id, EventType.FUNDS_WITHDRAWN, 2, Decimal("100.00"))
    proj = projector.apply_event(wdr)

    assert proj.balance == Decimal("0.00")
    assert proj.last_applied_sequence == 2


def test_domain_insufficient_funds_blocks_stream(projector: AccountProjector, opened_account, make_event):
    acc_id, _ = opened_account
    # Balance is 100.00, attempting to withdraw 100.01
    wdr = make_event(acc_id, EventType.FUNDS_WITHDRAWN, 2, Decimal("100.01"))
    with pytest.raises(InsufficientFundsError):
        projector.apply_event(wdr)

    proj = projector.get_projection(acc_id)
    assert proj is not None
    assert proj.balance == Decimal("100.00")
    assert proj.last_applied_sequence == 1
    assert proj.is_blocked is True
    assert proj.blocked_sequence_id == 2


def test_domain_multi_step_sequence(projector: AccountProjector, opened_account, make_event):
    acc_id, _ = opened_account
    # 100 -> +50 (150) -> -30 (120) -> +80 (200) -> -200 (0)
    p2 = projector.apply_event(make_event(acc_id, EventType.FUNDS_DEPOSITED, 2, Decimal("50.00")))
    assert p2.balance == Decimal("150.00")

    p3 = projector.apply_event(make_event(acc_id, EventType.FUNDS_WITHDRAWN, 3, Decimal("30.00")))
    assert p3.balance == Decimal("120.00")

    p4 = projector.apply_event(make_event(acc_id, EventType.FUNDS_DEPOSITED, 4, Decimal("80.00")))
    assert p4.balance == Decimal("200.00")

    p5 = projector.apply_event(make_event(acc_id, EventType.FUNDS_WITHDRAWN, 5, Decimal("200.00")))
    assert p5.balance == Decimal("0.00")
    assert p5.last_applied_sequence == 5

