"""Tests for state-transition atomicity and blocked-stream failure semantics (Task T05 Treatment Category 2)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from atavism_projection.projector import AccountProjector
from atavism_projection.types import (
    AccountFrozenError,
    AccountProjection,
    ConflictingEventError,
    EventType,
    InsufficientFundsError,
)


def test_blocked_stream_section_5_2_failure_walkthrough(projector: AccountProjector, make_event):
    """Exact implementation of the normative failure walkthrough from Section 5.2."""
    acc_id = "ACC-1"

    # 1. Sequence 1 arrives: Open account with $50.00
    ev1 = make_event(acc_id, EventType.ACCOUNT_OPENED, 1, Decimal("50.00"))
    p1 = projector.apply_event(ev1)
    assert p1 == AccountProjection(
        account_id=acc_id,
        balance=Decimal("50.00"),
        is_frozen=False,
        last_applied_sequence=1,
        pending_buffer_count=0,
        is_blocked=False,
        blocked_sequence_id=None,
    )

    # 2. Sequence 3 arrives out-of-order: Withdrawal of $80.00
    ev3 = make_event(acc_id, EventType.FUNDS_WITHDRAWN, 3, Decimal("80.00"))
    p3 = projector.apply_event(ev3)
    assert p3 == AccountProjection(
        account_id=acc_id,
        balance=Decimal("50.00"),
        is_frozen=False,
        last_applied_sequence=1,
        pending_buffer_count=1,
        is_blocked=False,
        blocked_sequence_id=None,
    )

    # 3. Sequence 4 arrives out-of-order: Deposit of $50.00
    ev4 = make_event(acc_id, EventType.FUNDS_DEPOSITED, 4, Decimal("50.00"))
    p4 = projector.apply_event(ev4)
    assert p4 == AccountProjection(
        account_id=acc_id,
        balance=Decimal("50.00"),
        is_frozen=False,
        last_applied_sequence=1,
        pending_buffer_count=2,
        is_blocked=False,
        blocked_sequence_id=None,
    )

    # 4. Sequence 2 arrives: Deposit of $20.00
    # Step 4a: Seq 2 commits ($70.00, last=2)
    # Step 4b: Drain attempts Seq 3: $80.00 > $70.00 -> InsufficientFundsError
    # Step 4c: Seq 3 evicted from buffer, identity retained
    # Step 4d: Account enters blocked state: is_blocked=True, blocked_seq=3
    # Step 4e: Seq 4 remains in buffer (no bypass)
    # Step 4f: InsufficientFundsError raised to caller
    ev2 = make_event(acc_id, EventType.FUNDS_DEPOSITED, 2, Decimal("20.00"))
    with pytest.raises(InsufficientFundsError):
        projector.apply_event(ev2)

    # 5. Query projection post-exception
    proj_post = projector.get_projection(acc_id)
    assert proj_post == AccountProjection(
        account_id=acc_id,
        balance=Decimal("70.00"),
        is_frozen=False,
        last_applied_sequence=2,
        pending_buffer_count=1,
        is_blocked=True,
        blocked_sequence_id=3,
    )

    # 6. Retry sequence 2 identically -> idempotent duplicate of applied event
    p2_retry = projector.apply_event(ev2)
    assert p2_retry == proj_post

    # 7. Retry sequence 3 identically -> deterministically fails against $70 balance
    with pytest.raises(InsufficientFundsError):
        projector.apply_event(ev3)

    proj_after_retry = projector.get_projection(acc_id)
    assert proj_after_retry == proj_post

    # 8. Conflicting retry of sequence 3 -> raises ConflictingEventError
    conflicting_ev3 = make_event(acc_id, EventType.FUNDS_WITHDRAWN, 3, Decimal("50.00"))
    with pytest.raises(ConflictingEventError):
        projector.apply_event(conflicting_ev3)

    # 9. Arrival of sequence 5 while blocked -> buffered, cannot bypass sequence 3
    ev5 = make_event(acc_id, EventType.FUNDS_DEPOSITED, 5, Decimal("30.00"))
    p5 = projector.apply_event(ev5)
    assert p5.balance == Decimal("70.00")
    assert p5.last_applied_sequence == 2
    assert p5.pending_buffer_count == 2
    assert p5.is_blocked is True
    assert p5.blocked_sequence_id == 3


def test_blocked_stream_drain_freeze_ordering_security(projector: AccountProjector, make_event):
    """Verifies that buffered monetary events cannot commit after a buffered freeze."""
    acc_id = "ACC-FREEZE-DRAIN"

    projector.apply_event(make_event(acc_id, EventType.ACCOUNT_OPENED, 1, Decimal("100.00")))

    # Buffer deposit at sequence 4
    projector.apply_event(make_event(acc_id, EventType.FUNDS_DEPOSITED, 4, Decimal("50.00")))
    # Buffer freeze at sequence 3
    projector.apply_event(make_event(acc_id, EventType.ACCOUNT_FROZEN, 3, reason="Court order"))

    # Deliver sequence 2
    ev2 = make_event(acc_id, EventType.FUNDS_DEPOSITED, 2, Decimal("25.00"))
    with pytest.raises(AccountFrozenError):
        projector.apply_event(ev2)

    proj = projector.get_projection(acc_id)
    assert proj is not None
    assert proj.balance == Decimal("125.00")  # 100 + 25
    assert proj.is_frozen is True
    assert proj.last_applied_sequence == 3
    assert proj.is_blocked is True
    assert proj.blocked_sequence_id == 4
    assert proj.pending_buffer_count == 0  # Evicted on domain failure


def test_blocked_stream_eviction_and_identity_retention(projector: AccountProjector, make_event):
    """Explicitly verifies Invariants 1, 2, 9, 10: eviction, identity retention, retry semantics."""
    acc_id = "ACC-EVICT"
    projector.apply_event(make_event(acc_id, EventType.ACCOUNT_OPENED, 1, Decimal("100.00")))

    # Buffer an overdraft withdrawal at sequence 3
    wdr3 = make_event(acc_id, EventType.FUNDS_WITHDRAWN, 3, Decimal("150.00"))
    projector.apply_event(wdr3)

    # Deliver sequence 2 deposit ($10.00) -> commits $110.00, then sequence 3 fails
    ev2 = make_event(acc_id, EventType.FUNDS_DEPOSITED, 2, Decimal("10.00"))
    with pytest.raises(InsufficientFundsError):
        projector.apply_event(ev2)

    proj = projector.get_projection(acc_id)
    assert proj is not None

    # Invariant 1: Failed buffered event is evicted from pending buffer
    assert proj.pending_buffer_count == 0

    # Invariant 2: Observed identity is retained (conflicting retry rejected)
    conflict_wdr3 = make_event(acc_id, EventType.FUNDS_WITHDRAWN, 3, Decimal("120.00"))
    with pytest.raises(ConflictingEventError):
        projector.apply_event(conflict_wdr3)

    # Invariant 9: Identical retry deterministically fails again
    with pytest.raises(InsufficientFundsError):
        projector.apply_event(wdr3)

    proj_retry = projector.get_projection(acc_id)
    assert proj_retry is not None
    assert proj_retry.is_blocked is True
    assert proj_retry.blocked_sequence_id == 3


def test_blocked_stream_causal_non_bypass_invariant(projector: AccountProjector, make_event):
    """Explicitly verifies Invariants 3, 4, 5, 6, 7, 8, 11: non-bypass and blockage persistence."""
    acc_id = "ACC-BYPASS"
    projector.apply_event(make_event(acc_id, EventType.ACCOUNT_OPENED, 1, Decimal("50.00")))

    # Buffer withdrawal at sequence 3 ($80.00)
    projector.apply_event(make_event(acc_id, EventType.FUNDS_WITHDRAWN, 3, Decimal("80.00")))

    # Buffer a large deposit at sequence 4 ($100.00)
    projector.apply_event(make_event(acc_id, EventType.FUNDS_DEPOSITED, 4, Decimal("100.00")))

    # Deliver sequence 2 ($20.00) -> commits $70.00, then sequence 3 fails
    with pytest.raises(InsufficientFundsError):
        projector.apply_event(make_event(acc_id, EventType.FUNDS_DEPOSITED, 2, Decimal("20.00")))

    proj = projector.get_projection(acc_id)
    assert proj is not None

    # Invariant 3: Prior commit is final ($70.00)
    assert proj.balance == Decimal("70.00")

    # Invariant 4: Last applied sequence remains at 2 (before failed sequence 3)
    assert proj.last_applied_sequence == 2

    # Invariant 5 & 6: Observable blocked state
    assert proj.is_blocked is True
    assert proj.blocked_sequence_id == 3

    # Invariant 7: Later buffered events remain pending
    assert proj.pending_buffer_count == 1

    # Invariant 8: Later events NEVER bypass the blocked sequence (balance is still $70.00, NOT $170.00)
    assert proj.balance == Decimal("70.00")

    # Invariant 11: New future events cannot advance or unblock the stream
    p5 = projector.apply_event(make_event(acc_id, EventType.FUNDS_DEPOSITED, 5, Decimal("200.00")))
    assert p5.balance == Decimal("70.00")
    assert p5.last_applied_sequence == 2
    assert p5.is_blocked is True
    assert p5.blocked_sequence_id == 3
    assert p5.pending_buffer_count == 2


