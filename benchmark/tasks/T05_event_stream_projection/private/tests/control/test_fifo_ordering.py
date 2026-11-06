"""Tests for Strict FIFO delivery contract (Task T05 Control Variant A)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from atavism_projection.projector import AccountProjector
from atavism_projection.types import (
    ConflictingEventError,
    EventType,
    InsufficientFundsError,
    InvalidEventSequenceError,
)


def test_fifo_ordering_gap_rejected_immediately(projector: AccountProjector, opened_account, make_event):
    acc_id, _ = opened_account
    # Account opened at sequence 1. Sequence 3 arrives with gap (missing sequence 2)
    gap_ev = make_event(acc_id, EventType.FUNDS_DEPOSITED, 3, Decimal("50.00"))

    with pytest.raises(InvalidEventSequenceError):
        projector.apply_event(gap_ev)

    # State must not be updated or buffered
    proj = projector.get_projection(acc_id)
    assert proj is not None
    assert proj.last_applied_sequence == 1
    assert proj.pending_buffer_count == 0
    assert proj.balance == Decimal("100.00")


def test_fifo_ordering_subsequent_contiguous_event_succeeds_after_gap_rejection(
    projector: AccountProjector, opened_account, make_event
):
    acc_id, _ = opened_account
    # Gap event rejected
    with pytest.raises(InvalidEventSequenceError):
        projector.apply_event(make_event(acc_id, EventType.FUNDS_DEPOSITED, 3, Decimal("50.00")))

    # Correct sequence 2 arrives
    seq2 = make_event(acc_id, EventType.FUNDS_DEPOSITED, 2, Decimal("30.00"))
    p2 = projector.apply_event(seq2)
    assert p2.last_applied_sequence == 2
    assert p2.balance == Decimal("130.00")

    # Sequence 3 now arrives and succeeds
    seq3 = make_event(acc_id, EventType.FUNDS_DEPOSITED, 3, Decimal("50.00"))
    p3 = projector.apply_event(seq3)
    assert p3.last_applied_sequence == 3
    assert p3.balance == Decimal("180.00")


def test_fifo_ordering_large_sequence_gap_rejected(projector: AccountProjector, opened_account, make_event):
    acc_id, _ = opened_account
    with pytest.raises(InvalidEventSequenceError):
        projector.apply_event(make_event(acc_id, EventType.FUNDS_DEPOSITED, 100, Decimal("10.00")))


def test_fifo_ordering_blocked_stream_retry_and_conflict(
    projector: AccountProjector, opened_account, make_event
):
    acc_id, _ = opened_account
    # Overdraft at sequence 2
    wdr = make_event(acc_id, EventType.FUNDS_WITHDRAWN, 2, Decimal("150.00"))
    with pytest.raises(InsufficientFundsError):
        projector.apply_event(wdr)

    proj = projector.get_projection(acc_id)
    assert proj is not None
    assert proj.is_blocked is True
    assert proj.blocked_sequence_id == 2
    assert proj.last_applied_sequence == 1

    # Identical retry re-fails deterministically
    with pytest.raises(InsufficientFundsError):
        projector.apply_event(wdr)

    # Conflicting retry raises ConflictingEventError
    conflicting_wdr = make_event(acc_id, EventType.FUNDS_WITHDRAWN, 2, Decimal("50.00"))
    with pytest.raises(ConflictingEventError):
        projector.apply_event(conflicting_wdr)


def test_fifo_ordering_gap_identity_retention_and_conflict(
    projector: AccountProjector, opened_account, make_event
):
    """Verifies that a FIFO gap event registers observed identity before rejection."""
    acc_id, _ = opened_account
    # 1. Sequence 3 arrives with gap (missing seq 2) -> rejected
    gap_ev = make_event(acc_id, EventType.FUNDS_DEPOSITED, 3, Decimal("50.00"))
    with pytest.raises(InvalidEventSequenceError):
        projector.apply_event(gap_ev)

    # 2. Conflicting redelivery of sequence 3 while still gapped raises ConflictingEventError
    conflict_gap_ev = make_event(acc_id, EventType.FUNDS_DEPOSITED, 3, Decimal("75.00"))
    with pytest.raises(ConflictingEventError):
        projector.apply_event(conflict_gap_ev)

    # 3. Missing sequence 2 arrives and commits
    seq2 = make_event(acc_id, EventType.FUNDS_DEPOSITED, 2, Decimal("30.00"))
    p2 = projector.apply_event(seq2)
    assert p2.last_applied_sequence == 2
    assert p2.balance == Decimal("130.00")

    # 4. Conflicting redelivery of sequence 3 after sequence 2 still raises ConflictingEventError
    with pytest.raises(ConflictingEventError):
        projector.apply_event(conflict_gap_ev)

    # 5. Original identical sequence 3 event now succeeds and commits
    p3 = projector.apply_event(gap_ev)
    assert p3.last_applied_sequence == 3
    assert p3.balance == Decimal("180.00")


def test_fifo_ordering_malformed_event_does_not_register_identity(
    projector: AccountProjector, opened_account, make_event
):
    """Verifies that events failing schema validation do not register observed identity."""
    acc_id, _ = opened_account
    # Malformed event at sequence 2 (negative amount)
    bad_ev = make_event(acc_id, EventType.FUNDS_DEPOSITED, 2, Decimal("-10.00"))
    with pytest.raises(Exception):
        projector.apply_event(bad_ev)

    # Valid event at sequence 2 arrives with positive amount: must succeed without conflict
    good_ev = make_event(acc_id, EventType.FUNDS_DEPOSITED, 2, Decimal("40.00"))
    p2 = projector.apply_event(good_ev)
    assert p2.last_applied_sequence == 2
    assert p2.balance == Decimal("140.00")


