"""Alternative Control Variant A reference implementation for Task T05.

Implements strict FIFO delivery with immediate sequence-gap rejection,
idempotent duplicate handling, and blocked-stream failure semantics
using a dispatch-table state machine architecture.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Callable

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


def _check_valid_event(ev: AccountEvent) -> None:
    if not isinstance(ev.account_id, str) or not ev.account_id.strip():
        raise EventValidationError("Invalid account_id: non-empty string required")

    if isinstance(ev.sequence_id, bool) or not isinstance(ev.sequence_id, int) or ev.sequence_id <= 0:
        raise EventValidationError("Invalid sequence_id: positive integer required")

    if not isinstance(ev.event_type, EventType):
        raise EventValidationError(f"Invalid event_type: {ev.event_type}")

    if ev.event_type == EventType.ACCOUNT_OPENED:
        if ev.sequence_id != 1:
            raise EventValidationError("ACCOUNT_OPENED must have sequence_id == 1")
        if ev.reason is not None:
            raise EventValidationError("ACCOUNT_OPENED must not have reason")
        if ev.amount is None or isinstance(ev.amount, bool) or not isinstance(ev.amount, Decimal):
            raise EventValidationError("ACCOUNT_OPENED amount must be a finite Decimal")
        if not ev.amount.is_finite() or ev.amount.as_tuple().exponent < -2:
            raise EventValidationError("ACCOUNT_OPENED amount must be finite with at most 2 decimal places")
        if ev.amount < Decimal("0.00"):
            raise EventValidationError("ACCOUNT_OPENED amount cannot be negative")

    elif ev.event_type == EventType.FUNDS_DEPOSITED:
        if ev.reason is not None:
            raise EventValidationError("FUNDS_DEPOSITED must not have reason")
        if ev.amount is None or isinstance(ev.amount, bool) or not isinstance(ev.amount, Decimal):
            raise EventValidationError("FUNDS_DEPOSITED amount must be a finite Decimal")
        if not ev.amount.is_finite() or ev.amount.as_tuple().exponent < -2:
            raise EventValidationError("FUNDS_DEPOSITED amount must be finite with at most 2 decimal places")
        if ev.amount <= Decimal("0.00"):
            raise EventValidationError("FUNDS_DEPOSITED amount must be strictly positive")

    elif ev.event_type == EventType.FUNDS_WITHDRAWN:
        if ev.reason is not None:
            raise EventValidationError("FUNDS_WITHDRAWN must not have reason")
        if ev.amount is None or isinstance(ev.amount, bool) or not isinstance(ev.amount, Decimal):
            raise EventValidationError("FUNDS_WITHDRAWN amount must be a finite Decimal")
        if not ev.amount.is_finite() or ev.amount.as_tuple().exponent < -2:
            raise EventValidationError("FUNDS_WITHDRAWN amount must be finite with at most 2 decimal places")
        if ev.amount <= Decimal("0.00"):
            raise EventValidationError("FUNDS_WITHDRAWN amount must be strictly positive")

    elif ev.event_type == EventType.ACCOUNT_FROZEN:
        if ev.amount is not None:
            raise EventValidationError("ACCOUNT_FROZEN must not have amount")
        if not isinstance(ev.reason, str) or not ev.reason.strip():
            raise EventValidationError("ACCOUNT_FROZEN must have a non-empty reason")


def _is_same_payload(a: AccountEvent, b: AccountEvent) -> bool:
    return (
        a.account_id == b.account_id
        and a.event_type == b.event_type
        and a.sequence_id == b.sequence_id
        and a.amount == b.amount
        and a.reason == b.reason
    )


class _AccountRecord:
    def __init__(self, account_id: str, initial_balance: Decimal) -> None:
        self.account_id = account_id
        self.balance = initial_balance
        self.is_frozen = False
        self.last_applied_sequence = 1
        self.is_blocked = False
        self.blocked_sequence_id: int | None = None
        self.history: dict[int, AccountEvent] = {}

    def snapshot(self) -> AccountProjection:
        return AccountProjection(
            account_id=self.account_id,
            balance=self.balance,
            is_frozen=self.is_frozen,
            last_applied_sequence=self.last_applied_sequence,
            pending_buffer_count=0,
            is_blocked=self.is_blocked,
            blocked_sequence_id=self.blocked_sequence_id,
        )


class AccountProjector:
    """Alternative Control Variant A reference implementation."""

    def __init__(self) -> None:
        self._records: dict[str, _AccountRecord] = {}
        self._handlers: dict[EventType, Callable[[_AccountRecord, AccountEvent], None]] = {
            EventType.FUNDS_DEPOSITED: self._handle_deposit,
            EventType.FUNDS_WITHDRAWN: self._handle_withdrawal,
            EventType.ACCOUNT_FROZEN: self._handle_freeze,
        }

    def _handle_deposit(self, record: _AccountRecord, event: AccountEvent) -> None:
        if record.is_frozen:
            record.is_blocked = True
            record.blocked_sequence_id = event.sequence_id
            raise AccountFrozenError(f"Deposit rejected: account {record.account_id} is frozen")
        record.balance += event.amount  # type: ignore[operator]
        record.last_applied_sequence = event.sequence_id
        record.is_blocked = False
        record.blocked_sequence_id = None

    def _handle_withdrawal(self, record: _AccountRecord, event: AccountEvent) -> None:
        if record.is_frozen:
            record.is_blocked = True
            record.blocked_sequence_id = event.sequence_id
            raise AccountFrozenError(f"Withdrawal rejected: account {record.account_id} is frozen")
        if event.amount > record.balance:  # type: ignore[operator]
            record.is_blocked = True
            record.blocked_sequence_id = event.sequence_id
            raise InsufficientFundsError(
                f"Withdrawal of {event.amount} exceeds available balance {record.balance}"
            )
        record.balance -= event.amount  # type: ignore[operator]
        record.last_applied_sequence = event.sequence_id
        record.is_blocked = False
        record.blocked_sequence_id = None

    def _handle_freeze(self, record: _AccountRecord, event: AccountEvent) -> None:
        record.is_frozen = True
        record.last_applied_sequence = event.sequence_id
        record.is_blocked = False
        record.blocked_sequence_id = None

    def apply_event(self, event: AccountEvent) -> AccountProjection:
        _check_valid_event(event)
        aid = event.account_id

        if aid not in self._records:
            if event.event_type != EventType.ACCOUNT_OPENED:
                raise AccountNotOpenedError(f"Account {aid} does not exist")
            record = _AccountRecord(aid, event.amount)  # type: ignore[arg-type]
            record.history[1] = event
            self._records[aid] = record
            return record.snapshot()

        record = self._records[aid]

        if event.sequence_id in record.history:
            existing = record.history[event.sequence_id]
            if not _is_same_payload(event, existing):
                raise ConflictingEventError(
                    f"Conflict at sequence {event.sequence_id} for account {aid}"
                )
            if event.sequence_id <= record.last_applied_sequence:
                return record.snapshot()
            if record.is_blocked and event.sequence_id == record.blocked_sequence_id:
                # Deterministic retry of blocked sequence
                handler = self._handlers[event.event_type]
                handler(record, event)
                return record.snapshot()

        if event.event_type == EventType.ACCOUNT_OPENED:
            raise AccountAlreadyOpenedError(f"Account {aid} already initialized")

        record.history[event.sequence_id] = event

        expected = record.last_applied_sequence + 1
        if event.sequence_id > expected:
            raise InvalidEventSequenceError(
                f"Strict FIFO contract violation: expected {expected}, got {event.sequence_id}"
            )

        handler = self._handlers[event.event_type]
        handler(record, event)
        return record.snapshot()

    def get_projection(self, account_id: str) -> AccountProjection | None:
        record = self._records.get(account_id)
        if record is None:
            return None
        return record.snapshot()

