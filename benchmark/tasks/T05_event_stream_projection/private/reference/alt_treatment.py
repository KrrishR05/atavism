"""Alternative Treatment Variant B reference implementation for Task T05.

Implements at-least-once out-of-order event delivery with priority-queue
buffer draining, idempotent duplicate tracking, invalid event eviction,
and persistent blocked stream state.
"""

from __future__ import annotations

import heapq
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
)


def _validate_incoming_event(ev: AccountEvent) -> None:
    if not isinstance(ev.account_id, str) or not ev.account_id.strip():
        raise EventValidationError("Account ID must be a non-empty string")

    if isinstance(ev.sequence_id, bool) or not isinstance(ev.sequence_id, int) or ev.sequence_id <= 0:
        raise EventValidationError("Sequence ID must be a strictly positive integer")

    if not isinstance(ev.event_type, EventType):
        raise EventValidationError(f"Invalid EventType: {ev.event_type}")

    if ev.event_type == EventType.ACCOUNT_OPENED:
        if ev.sequence_id != 1:
            raise EventValidationError("ACCOUNT_OPENED must have sequence ID 1")
        if ev.reason is not None:
            raise EventValidationError("ACCOUNT_OPENED reason must be None")
        if ev.amount is None or isinstance(ev.amount, bool) or not isinstance(ev.amount, Decimal):
            raise EventValidationError("ACCOUNT_OPENED amount must be a finite Decimal")
        if not ev.amount.is_finite() or ev.amount.as_tuple().exponent < -2:
            raise EventValidationError("ACCOUNT_OPENED amount must be finite with <= 2 decimal places")
        if ev.amount < Decimal("0.00"):
            raise EventValidationError("ACCOUNT_OPENED initial balance cannot be negative")

    elif ev.event_type in (EventType.FUNDS_DEPOSITED, EventType.FUNDS_WITHDRAWN):
        if ev.reason is not None:
            raise EventValidationError(f"{ev.event_type.value} reason must be None")
        if ev.amount is None or isinstance(ev.amount, bool) or not isinstance(ev.amount, Decimal):
            raise EventValidationError(f"{ev.event_type.value} amount must be a finite Decimal")
        if not ev.amount.is_finite() or ev.amount.as_tuple().exponent < -2:
            raise EventValidationError(f"{ev.event_type.value} amount must be finite with <= 2 decimal places")
        if ev.amount <= Decimal("0.00"):
            raise EventValidationError(f"{ev.event_type.value} amount must be positive")

    elif ev.event_type == EventType.ACCOUNT_FROZEN:
        if ev.amount is not None:
            raise EventValidationError("ACCOUNT_FROZEN amount must be None")
        if not isinstance(ev.reason, str) or not ev.reason.strip():
            raise EventValidationError("ACCOUNT_FROZEN reason must be a non-empty string")


def _is_equivalent(e1: AccountEvent, e2: AccountEvent) -> bool:
    return (
        e1.account_id == e2.account_id
        and e1.event_type == e2.event_type
        and e1.sequence_id == e2.sequence_id
        and e1.amount == e2.amount
        and e1.reason == e2.reason
    )


class _PriorityBufferAccount:
    def __init__(self, account_id: str, opening_amount: Decimal) -> None:
        self.account_id = account_id
        self.balance = opening_amount
        self.is_frozen = False
        self.last_applied_sequence = 1
        self.is_blocked = False
        self.blocked_sequence_id: int | None = None
        self.observed: dict[int, AccountEvent] = {}
        # Buffer indexed by sequence_id
        self.pending: dict[int, AccountEvent] = {}

    def to_projection(self) -> AccountProjection:
        return AccountProjection(
            account_id=self.account_id,
            balance=self.balance,
            is_frozen=self.is_frozen,
            last_applied_sequence=self.last_applied_sequence,
            pending_buffer_count=len(self.pending),
            is_blocked=self.is_blocked,
            blocked_sequence_id=self.blocked_sequence_id,
        )


class AccountProjector:
    """Alternative Treatment Variant B reference implementation."""

    def __init__(self) -> None:
        self._accounts: dict[str, _PriorityBufferAccount] = {}

    def apply_event(self, event: AccountEvent) -> AccountProjection:
        _validate_incoming_event(event)
        aid = event.account_id

        if aid not in self._accounts:
            if event.event_type != EventType.ACCOUNT_OPENED:
                raise AccountNotOpenedError(f"Account {aid} does not exist")
            acct = _PriorityBufferAccount(aid, event.amount)  # type: ignore[arg-type]
            acct.observed[1] = event
            self._accounts[aid] = acct
            return acct.to_projection()

        acct = self._accounts[aid]

        # Duplicate checking against observed registry
        if event.sequence_id in acct.observed:
            prev = acct.observed[event.sequence_id]
            if not _is_equivalent(event, prev):
                raise ConflictingEventError(
                    f"Conflicting payload for sequence {event.sequence_id} on {aid}"
                )
            if event.sequence_id <= acct.last_applied_sequence:
                return acct.to_projection()
            if event.sequence_id in acct.pending:
                return acct.to_projection()
            if acct.is_blocked and event.sequence_id == acct.blocked_sequence_id:
                return self._apply_and_drain(acct, event)

        if event.event_type == EventType.ACCOUNT_OPENED:
            raise AccountAlreadyOpenedError(f"Account {aid} is already opened")

        acct.observed[event.sequence_id] = event

        if event.sequence_id > acct.last_applied_sequence + 1:
            acct.pending[event.sequence_id] = event
            return acct.to_projection()

        return self._apply_and_drain(acct, event)

    def _apply_and_drain(self, acct: _PriorityBufferAccount, event: AccountEvent) -> AccountProjection:
        try:
            self._apply_atomic(acct, event)
        except (InsufficientFundsError, AccountFrozenError) as exc:
            acct.is_blocked = True
            acct.blocked_sequence_id = event.sequence_id
            raise exc

        acct.is_blocked = False
        acct.blocked_sequence_id = None

        while (acct.last_applied_sequence + 1) in acct.pending:
            next_seq = acct.last_applied_sequence + 1
            next_ev = acct.pending[next_seq]
            try:
                self._apply_atomic(acct, next_ev)
                del acct.pending[next_seq]
            except (InsufficientFundsError, AccountFrozenError) as exc:
                del acct.pending[next_seq]
                acct.is_blocked = True
                acct.blocked_sequence_id = next_seq
                raise exc

        return acct.to_projection()

    def _apply_atomic(self, acct: _PriorityBufferAccount, event: AccountEvent) -> None:
        if acct.is_frozen and event.event_type in (EventType.FUNDS_DEPOSITED, EventType.FUNDS_WITHDRAWN):
            raise AccountFrozenError(f"Account {acct.account_id} is frozen")

        if event.event_type == EventType.FUNDS_DEPOSITED:
            acct.balance += event.amount  # type: ignore[operator]
            acct.last_applied_sequence = event.sequence_id
        elif event.event_type == EventType.FUNDS_WITHDRAWN:
            if event.amount > acct.balance:  # type: ignore[operator]
                raise InsufficientFundsError(f"Insufficient funds: {event.amount} > {acct.balance}")
            acct.balance -= event.amount  # type: ignore[operator]
            acct.last_applied_sequence = event.sequence_id
        elif event.event_type == EventType.ACCOUNT_FROZEN:
            acct.is_frozen = True
            acct.last_applied_sequence = event.sequence_id

    def get_projection(self, account_id: str) -> AccountProjection | None:
        acct = self._accounts.get(account_id)
        if acct is None:
            return None
        return acct.to_projection()

