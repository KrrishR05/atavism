"""Tests for out-of-order event buffering and contiguous draining (Task T05 Treatment Category 1)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from atavism_projection.projector import AccountProjector
from atavism_projection.types import (
    ConflictingEventError,
    EventType,
)


def test_buffering_and_draining_single_out_of_order_event(projector: AccountProjector, opened_account, make_event):
    acc_id, _ = opened_account
    # Account opened at seq 1 with $100. Seq 3 arrives out-of-order
    ev3 = make_event(acc_id, EventType.FUNDS_DEPOSITED, 3, Decimal("50.00"))
    p3 = projector.apply_event(ev3)

    assert p3.balance == Decimal("100.00")
    assert p3.last_applied_sequence == 1
    assert p3.pending_buffer_count == 1
    assert p3.is_blocked is False

    # Seq 2 arrives, triggering drain of Seq 2 and Seq 3
    ev2 = make_event(acc_id, EventType.FUNDS_DEPOSITED, 2, Decimal("25.00"))
    p2 = projector.apply_event(ev2)

    assert p2.balance == Decimal("175.00")  # 100 + 25 + 50
    assert p2.last_applied_sequence == 3
    assert p2.pending_buffer_count == 0
    assert p2.is_blocked is False


def test_buffering_and_draining_multi_event_reverse_order(projector: AccountProjector, opened_account, make_event):
    acc_id, _ = opened_account
    # Arrive: 5, 4, 3
    projector.apply_event(make_event(acc_id, EventType.FUNDS_DEPOSITED, 5, Decimal("10.00")))
    projector.apply_event(make_event(acc_id, EventType.FUNDS_DEPOSITED, 4, Decimal("20.00")))
    p_buf = projector.apply_event(make_event(acc_id, EventType.FUNDS_DEPOSITED, 3, Decimal("30.00")))

    assert p_buf.balance == Decimal("100.00")
    assert p_buf.last_applied_sequence == 1
    assert p_buf.pending_buffer_count == 3

    # Sequence 2 arrives and unleashes full contiguous chain 2->3->4->5
    p_final = projector.apply_event(make_event(acc_id, EventType.FUNDS_DEPOSITED, 2, Decimal("40.00")))

    assert p_final.balance == Decimal("200.00")  # 100 + 40 + 30 + 20 + 10
    assert p_final.last_applied_sequence == 5
    assert p_final.pending_buffer_count == 0


def test_buffering_and_draining_partial_drain_with_remaining_gap(
    projector: AccountProjector, opened_account, make_event
):
    acc_id, _ = opened_account
    # Buffer 4 and 5
    projector.apply_event(make_event(acc_id, EventType.FUNDS_DEPOSITED, 4, Decimal("15.00")))
    projector.apply_event(make_event(acc_id, EventType.FUNDS_DEPOSITED, 5, Decimal("25.00")))

    # Sequence 2 arrives: applies 2, but gap at 3 halts draining
    p2 = projector.apply_event(make_event(acc_id, EventType.FUNDS_DEPOSITED, 2, Decimal("10.00")))
    assert p2.balance == Decimal("110.00")
    assert p2.last_applied_sequence == 2
    assert p2.pending_buffer_count == 2

    # Now sequence 3 arrives: drains 3, 4, 5
    p3 = projector.apply_event(make_event(acc_id, EventType.FUNDS_DEPOSITED, 3, Decimal("5.00")))
    assert p3.balance == Decimal("155.00")  # 110 + 5 + 15 + 25
    assert p3.last_applied_sequence == 5
    assert p3.pending_buffer_count == 0


def test_buffering_and_draining_duplicate_buffered_event_handling(
    projector: AccountProjector, opened_account, make_event
):
    acc_id, _ = opened_account
    ev3 = make_event(acc_id, EventType.FUNDS_DEPOSITED, 3, Decimal("50.00"))
    p1 = projector.apply_event(ev3)
    assert p1.pending_buffer_count == 1

    # Identical redelivery while in buffer
    p2 = projector.apply_event(ev3)
    assert p2.pending_buffer_count == 1
    assert p2.balance == Decimal("100.00")

    # Conflicting redelivery while in buffer raises ConflictingEventError
    conflict_ev3 = make_event(acc_id, EventType.FUNDS_DEPOSITED, 3, Decimal("60.00"))
    with pytest.raises(ConflictingEventError):
        projector.apply_event(conflict_ev3)


def test_buffering_cross_account_buffer_isolation(projector: AccountProjector, make_event):
    projector.apply_event(make_event("ACC-X", EventType.ACCOUNT_OPENED, 1, Decimal("100.00")))
    projector.apply_event(make_event("ACC-Y", EventType.ACCOUNT_OPENED, 1, Decimal("100.00")))

    # Buffer seq 3 on ACC-X
    projector.apply_event(make_event("ACC-X", EventType.FUNDS_DEPOSITED, 3, Decimal("50.00")))

    # ACC-Y receives seq 2
    p_y = projector.apply_event(make_event("ACC-Y", EventType.FUNDS_DEPOSITED, 2, Decimal("20.00")))

    # ACC-Y should only have seq 2 applied, no seq 3 drained from ACC-X!
    assert p_y.balance == Decimal("120.00")
    assert p_y.last_applied_sequence == 2
    assert p_y.pending_buffer_count == 0

    # ACC-X still has its buffer intact
    p_x = projector.get_projection("ACC-X")
    assert p_x is not None
    assert p_x.balance == Decimal("100.00")
    assert p_x.pending_buffer_count == 1

