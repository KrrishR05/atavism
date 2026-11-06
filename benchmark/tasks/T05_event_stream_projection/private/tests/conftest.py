"""Shared pytest fixtures for Task T05 event stream projection tests."""

from __future__ import annotations

from decimal import Decimal

import pytest
from atavism_projection.projector import AccountProjector
from atavism_projection.types import (
    AccountEvent,
    EventType,
)


@pytest.fixture
def projector() -> AccountProjector:
    """Provides a fresh, clean instance of AccountProjector."""
    return AccountProjector()


@pytest.fixture
def make_event():
    """Factory fixture for creating AccountEvent instances."""
    def _make(
        account_id: str,
        event_type: EventType,
        sequence_id: int,
        amount: Decimal | str | None = None,
        reason: str | None = None,
    ) -> AccountEvent:
        dec_amount = Decimal(str(amount)) if (amount is not None and not isinstance(amount, Decimal)) else amount
        return AccountEvent(
            account_id=account_id,
            event_type=event_type,
            sequence_id=sequence_id,
            amount=dec_amount,  # type: ignore[arg-type]
            reason=reason,
        )
    return _make


@pytest.fixture
def opened_account(projector: AccountProjector, make_event):
    """Initializes a standard test account ACC-1 with balance $100.00 at sequence 1."""
    open_ev = make_event("ACC-1", EventType.ACCOUNT_OPENED, 1, Decimal("100.00"))
    proj = projector.apply_event(open_ev)
    return "ACC-1", proj

