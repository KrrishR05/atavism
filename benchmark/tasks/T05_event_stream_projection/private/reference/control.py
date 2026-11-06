"""Control Variant A reference implementation for Task T05.

Implements strict FIFO delivery with immediate sequence-gap rejection,
idempotent duplicate handling, domain state transitions, and persistent
blocked stream semantics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from atavism_projection.types import (
    AccountAlreadyOpenedError,
    AccountEvent,
    AccountFrozenError,
    AccountNotOpenedError,
    AccountProjection,
    ConflictingEventError,
    EventType,
    EventValidationError,
    InsufficientFundsError,
    InvalidEventSequenceError,
)


@dataclass
class _AccountState:
    account_id: str
    balance: Decimal = Decimal("0.00")
    is_frozen: bool = False
    last_applied_sequence: int = 0
    is_blocked: bool = False
    blocked_sequence_id: int | None = None
    observed_events: dict[int, AccountEvent] = field(default_factory=dict)


def _validate_event(event: AccountEvent) -> None:
    if not isinstance(event.account_id, str) or not event.account_id.strip():
        raise EventValidationError("account_id must be a non-empty, non-whitespace string")

    # Sequence ID must be strictly positive int and NOT a bool
    if isinstance(event.sequence_id, bool) or not isinstance(event.sequence_id, int) or event.sequence_id <= 0:
        raise EventValidationError("sequence_id must be a strictly positive integer")

    if not isinstance(event.event_type, EventType):
        raise EventValidationError("event_type must be a valid EventType")

    if event.event_type == EventType.ACCOUNT_OPENED:
        if event.sequence_id != 1:
            raise EventValidationError("ACCOUNT_OPENED sequence_id must be strictly 1")
        if event.reason is not None:
            raise EventValidationError("ACCOUNT_OPENED reason must be None")
        if event.amount is None or isinstance(event.amount, bool) or not isinstance(event.amount, Decimal):
            raise EventValidationError("ACCOUNT_OPENED amount must be a finite Decimal")
        if not event.amount.is_finite():
            raise EventValidationError("ACCOUNT_OPENED amount must be finite")
        if event.amount.as_tuple().exponent < -2:
            raise EventValidationError("ACCOUNT_OPENED amount may have at most two decimal places")
        if event.amount < Decimal("0.00"):
            raise EventValidationError("ACCOUNT_OPENED amount must be non-negative")

    elif event.event_type == EventType.FUNDS_DEPOSITED:
        if event.reason is not None:
            raise EventValidationError("FUNDS_DEPOSITED reason must be None")
        if event.amount is None or isinstance(event.amount, bool) or not isinstance(event.amount, Decimal):
            raise EventValidationError("FUNDS_DEPOSITED amount must be a finite Decimal")
        if not event.amount.is_finite():
            raise EventValidationError("FUNDS_DEPOSITED amount must be finite")
        if event.amount.as_tuple().exponent < -2:
            raise EventValidationError("FUNDS_DEPOSITED amount may have at most two decimal places")
        if event.amount <= Decimal("0.00"):
            raise EventValidationError("FUNDS_DEPOSITED amount must be strictly positive")

    elif event.event_type == EventType.FUNDS_WITHDRAWN:
        if event.reason is not None:
            raise EventValidationError("FUNDS_WITHDRAWN reason must be None")
        if event.amount is None or isinstance(event.amount, bool) or not isinstance(event.amount, Decimal):
            raise EventValidationError("FUNDS_WITHDRAWN amount must be a finite Decimal")
        if not event.amount.is_finite():
            raise EventValidationError("FUNDS_WITHDRAWN amount must be finite")
        if event.amount.as_tuple().exponent < -2:
            raise EventValidationError("FUNDS_WITHDRAWN amount may have at most two decimal places")
        if event.amount <= Decimal("0.00"):
            raise EventValidationError("FUNDS_WITHDRAWN amount must be strictly positive")

    elif event.event_type == EventType.ACCOUNT_FROZEN:
        if event.amount is not None:
            raise EventValidationError("ACCOUNT_FROZEN amount must be None")
        if not isinstance(event.reason, str) or not event.reason.strip():
            raise EventValidationError("ACCOUNT_FROZEN reason must be a non-empty string")


def _is_identical_payload(e1: AccountEvent, e2: AccountEvent) -> bool:
    return (
        e1.account_id == e2.account_id
        and e1.event_type == e2.event_type
        and e1.sequence_id == e2.sequence_id
        and e1.amount == e2.amount
        and e1.reason == e2.reason
    )


class AccountProjector:
    """Control Variant A reference implementation."""

    def __init__(self) -> None:
        self._accounts: dict[str, _AccountState] = {}

    def apply_event(self, event: AccountEvent) -> AccountProjection:
        _validate_event(event)
        account_id = event.account_id

        if account_id not in self._accounts:
            if event.event_type != EventType.ACCOUNT_OPENED:
                raise AccountNotOpenedError(f"Account {account_id} has not been opened")
            # Opening event at sequence 1
            state = _AccountState(
                account_id=account_id,
                balance=event.amount,  # type: ignore[arg-type]
                is_frozen=False,
                last_applied_sequence=1,
                is_blocked=False,
                blocked_sequence_id=None,
            )
            state.observed_events[1] = event
            self._accounts[account_id] = state
            return self._to_projection(state)

        state = self._accounts[account_id]

        # Duplicate checking against observed event registry
        if event.sequence_id in state.observed_events:
            prev = state.observed_events[event.sequence_id]
            if not _is_identical_payload(event, prev):
                raise ConflictingEventError(
                    f"Conflicting payload for sequence {event.sequence_id} on account {account_id}"
                )
            # Identical payload
            if event.sequence_id <= state.last_applied_sequence:
                return self._to_projection(state)
            if state.is_blocked and event.sequence_id == state.blocked_sequence_id:
                # Deterministic re-evaluation of blocked sequence
                return self._apply_transition(state, event)

        # Opening event received on already opened account
        if event.event_type == EventType.ACCOUNT_OPENED:
            raise AccountAlreadyOpenedError(f"Account {account_id} is already opened")

        # FIFO sequence validation
        expected_seq = state.last_applied_sequence + 1
        if event.sequence_id > expected_seq:
            raise InvalidEventSequenceError(
                f"FIFO violation: expected sequence {expected_seq}, received {event.sequence_id}"
            )

        # Record observed identity
        state.observed_events[event.sequence_id] = event
        return self._apply_transition(state, event)

    def _apply_transition(self, state: _AccountState, event: AccountEvent) -> AccountProjection:
        if state.is_frozen and event.event_type in (EventType.FUNDS_DEPOSITED, EventType.FUNDS_WITHDRAWN):
            state.is_blocked = True
            state.blocked_sequence_id = event.sequence_id
            raise AccountFrozenError(f"Cannot perform monetary operation on frozen account {state.account_id}")

        if event.event_type == EventType.FUNDS_DEPOSITED:
            state.balance += event.amount  # type: ignore[operator]
            state.last_applied_sequence = event.sequence_id
            state.is_blocked = False
            state.blocked_sequence_id = None
        elif event.event_type == EventType.FUNDS_WITHDRAWN:
            if event.amount > state.balance:  # type: ignore[operator]
                state.is_blocked = True
                state.blocked_sequence_id = event.sequence_id
                raise InsufficientFundsError(f"Insufficient funds for withdrawal of {event.amount}")
            state.balance -= event.amount  # type: ignore[operator]
            state.last_applied_sequence = event.sequence_id
            state.is_blocked = False
            state.blocked_sequence_id = None
        elif event.event_type == EventType.ACCOUNT_FROZEN:
            state.is_frozen = True
            state.last_applied_sequence = event.sequence_id
            state.is_blocked = False
            state.blocked_sequence_id = None

        return self._to_projection(state)

    def get_projection(self, account_id: str) -> AccountProjection | None:
        state = self._accounts.get(account_id)
        if state is None:
            return None
        return self._to_projection(state)

    def _to_projection(self, state: _AccountState) -> AccountProjection:
        return AccountProjection(
            account_id=state.account_id,
            balance=state.balance,
            is_frozen=state.is_frozen,
            last_applied_sequence=state.last_applied_sequence,
            pending_buffer_count=0,
            is_blocked=state.is_blocked,
            blocked_sequence_id=state.blocked_sequence_id,
        )

