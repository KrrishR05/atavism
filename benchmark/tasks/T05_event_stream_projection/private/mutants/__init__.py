"""Mutation fixtures for Atavism T05 (Out-of-Order Event Stream Projection Protocol).

Each mutant introduces a specific behavioral defect or anti-pattern to verify
the sensitivity and specificity of the test suites.
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
)


@dataclass
class _BaseAccountState:
    account_id: str
    balance: Decimal = Decimal("0.00")
    is_frozen: bool = False
    last_applied_sequence: int = 0
    is_blocked: bool = False
    blocked_sequence_id: int | None = None
    pending_buffer: dict[int, AccountEvent] = field(default_factory=dict)
    observed_events: dict[int, AccountEvent] = field(default_factory=dict)


def _base_validate(event: AccountEvent) -> None:
    if not isinstance(event.account_id, str) or not event.account_id.strip():
        raise EventValidationError("account_id must be a non-empty string")
    if isinstance(event.sequence_id, bool) or not isinstance(event.sequence_id, int) or event.sequence_id <= 0:
        raise EventValidationError("sequence_id must be a positive integer")
    if not isinstance(event.event_type, EventType):
        raise EventValidationError("event_type must be a valid EventType")

    if event.event_type == EventType.ACCOUNT_OPENED:
        if event.sequence_id != 1:
            raise EventValidationError("ACCOUNT_OPENED sequence_id must be 1")
        if event.reason is not None:
            raise EventValidationError("ACCOUNT_OPENED reason must be None")
        if event.amount is None or isinstance(event.amount, bool) or not isinstance(event.amount, Decimal):
            raise EventValidationError("ACCOUNT_OPENED amount must be a finite Decimal")
        if not event.amount.is_finite() or event.amount.as_tuple().exponent < -2:
            raise EventValidationError("ACCOUNT_OPENED amount must be finite with <= 2 decimal places")
        if event.amount < Decimal("0.00"):
            raise EventValidationError("ACCOUNT_OPENED amount must be non-negative")

    elif event.event_type in (EventType.FUNDS_DEPOSITED, EventType.FUNDS_WITHDRAWN):
        if event.reason is not None:
            raise EventValidationError(f"{event.event_type.value} reason must be None")
        if event.amount is None or isinstance(event.amount, bool) or not isinstance(event.amount, Decimal):
            raise EventValidationError(f"{event.event_type.value} amount must be a finite Decimal")
        if not event.amount.is_finite() or event.amount.as_tuple().exponent < -2:
            raise EventValidationError(f"{event.event_type.value} amount must be finite with <= 2 decimal places")
        if event.amount <= Decimal("0.00"):
            raise EventValidationError(f"{event.event_type.value} amount must be strictly positive")

    elif event.event_type == EventType.ACCOUNT_FROZEN:
        if event.amount is not None:
            raise EventValidationError("ACCOUNT_FROZEN amount must be None")
        if not isinstance(event.reason, str) or not event.reason.strip():
            raise EventValidationError("ACCOUNT_FROZEN reason must be a non-empty string")


def _is_identical(e1: AccountEvent, e2: AccountEvent) -> bool:
    return (
        e1.account_id == e2.account_id
        and e1.event_type == e2.event_type
        and e1.sequence_id == e2.sequence_id
        and e1.amount == e2.amount
        and e1.reason == e2.reason
    )


class BaseProjector:
    """Base Treatment B implementation used by mutants."""

    def __init__(self) -> None:
        self._accounts: dict[str, _BaseAccountState] = {}

    def get_projection(self, account_id: str) -> AccountProjection | None:
        state = self._accounts.get(account_id)
        if state is None:
            return None
        return self._to_projection(state)

    def _to_projection(self, state: _BaseAccountState) -> AccountProjection:
        return AccountProjection(
            account_id=state.account_id,
            balance=state.balance,
            is_frozen=state.is_frozen,
            last_applied_sequence=state.last_applied_sequence,
            pending_buffer_count=len(state.pending_buffer),
            is_blocked=state.is_blocked,
            blocked_sequence_id=state.blocked_sequence_id,
        )

    def apply_event(self, event: AccountEvent) -> AccountProjection:
        _base_validate(event)
        aid = event.account_id
        if aid not in self._accounts:
            if event.event_type != EventType.ACCOUNT_OPENED:
                raise AccountNotOpenedError(f"Account {aid} not opened")
            st = _BaseAccountState(account_id=aid, balance=event.amount, last_applied_sequence=1)  # type: ignore[arg-type]
            st.observed_events[1] = event
            self._accounts[aid] = st
            return self._to_projection(st)

        st = self._accounts[aid]
        if event.sequence_id in st.observed_events:
            prev = st.observed_events[event.sequence_id]
            if not _is_identical(event, prev):
                raise ConflictingEventError(f"Conflict on sequence {event.sequence_id}")
            if event.sequence_id <= st.last_applied_sequence:
                return self._to_projection(st)
            if event.sequence_id in st.pending_buffer:
                return self._to_projection(st)
            if st.is_blocked and event.sequence_id == st.blocked_sequence_id:
                return self._execute_and_drain(st, event)

        if event.event_type == EventType.ACCOUNT_OPENED:
            raise AccountAlreadyOpenedError(f"Account {aid} already opened")

        st.observed_events[event.sequence_id] = event

        if event.sequence_id > st.last_applied_sequence + 1:
            st.pending_buffer[event.sequence_id] = event
            return self._to_projection(st)

        return self._execute_and_drain(st, event)

    def _execute_and_drain(self, state: _BaseAccountState, event: AccountEvent) -> AccountProjection:
        try:
            self._apply_single_event(state, event)
        except (InsufficientFundsError, AccountFrozenError) as err:
            state.is_blocked = True
            state.blocked_sequence_id = event.sequence_id
            raise err

        state.is_blocked = False
        state.blocked_sequence_id = None

        while (state.last_applied_sequence + 1) in state.pending_buffer:
            next_seq = state.last_applied_sequence + 1
            next_ev = state.pending_buffer[next_seq]
            try:
                self._apply_single_event(state, next_ev)
                del state.pending_buffer[next_seq]
            except (InsufficientFundsError, AccountFrozenError) as err:
                del state.pending_buffer[next_seq]
                state.is_blocked = True
                state.blocked_sequence_id = next_seq
                raise err

        return self._to_projection(state)

    def _apply_single_event(self, state: _BaseAccountState, event: AccountEvent) -> None:
        if state.is_frozen and event.event_type in (EventType.FUNDS_DEPOSITED, EventType.FUNDS_WITHDRAWN):
            raise AccountFrozenError(f"Account {state.account_id} is frozen")
        if event.event_type == EventType.FUNDS_DEPOSITED:
            state.balance += event.amount  # type: ignore[operator]
            state.last_applied_sequence = event.sequence_id
        elif event.event_type == EventType.FUNDS_WITHDRAWN:
            if event.amount > state.balance:  # type: ignore[operator]
                raise InsufficientFundsError("Insufficient funds")
            state.balance -= event.amount  # type: ignore[operator]
            state.last_applied_sequence = event.sequence_id
        elif event.event_type == EventType.ACCOUNT_FROZEN:
            state.is_frozen = True
            state.last_applied_sequence = event.sequence_id


# ---------------------------------------------------------------------------
# 10 MUTANTS FOR TASK T05
# ---------------------------------------------------------------------------

class MutantDropFutureEvents(BaseProjector):
    """MUTANT 1: Discards out-of-order events instead of buffering in Treatment B."""

    def apply_event(self, event: AccountEvent) -> AccountProjection:
        _base_validate(event)
        aid = event.account_id
        if aid not in self._accounts:
            return super().apply_event(event)

        st = self._accounts[aid]
        if event.sequence_id in st.observed_events:
            return super().apply_event(event)

        if event.event_type == EventType.ACCOUNT_OPENED:
            raise AccountAlreadyOpenedError(f"Account {aid} already opened")

        st.observed_events[event.sequence_id] = event

        # FLAW: Drops out-of-order events without buffering
        if event.sequence_id > st.last_applied_sequence + 1:
            return self._to_projection(st)

        return self._execute_and_drain(st, event)


class MutantPrematureApplication(BaseProjector):
    """MUTANT 2: Immediately applies out-of-order events instead of buffering."""

    def apply_event(self, event: AccountEvent) -> AccountProjection:
        _base_validate(event)
        aid = event.account_id
        if aid not in self._accounts:
            return super().apply_event(event)

        st = self._accounts[aid]
        if event.sequence_id in st.observed_events:
            return super().apply_event(event)

        if event.event_type == EventType.ACCOUNT_OPENED:
            raise AccountAlreadyOpenedError(f"Account {aid} already opened")

        st.observed_events[event.sequence_id] = event

        # FLAW: Applies event immediately regardless of sequence order
        self._apply_single_event(st, event)
        return self._to_projection(st)


class MutantReplayDuplicate(BaseProjector):
    """MUTANT 3: Re-applies duplicate events mutating balance instead of idempotent return."""

    def apply_event(self, event: AccountEvent) -> AccountProjection:
        _base_validate(event)
        aid = event.account_id
        if aid in self._accounts:
            st = self._accounts[aid]
            if event.sequence_id in st.observed_events:
                # FLAW: Re-applies duplicate instead of returning idempotent snapshot
                self._apply_single_event(st, event)
                return self._to_projection(st)
        return super().apply_event(event)


class MutantAcceptConflict(BaseProjector):
    """MUTANT 4: Silently accepts conflicting duplicate payloads."""

    def apply_event(self, event: AccountEvent) -> AccountProjection:
        _base_validate(event)
        aid = event.account_id
        if aid in self._accounts:
            st = self._accounts[aid]
            if event.sequence_id in st.observed_events:
                # FLAW: Does not check for conflict! Silently returns projection
                return self._to_projection(st)
        return super().apply_event(event)


class MutantCrossAccountBufferLeak(BaseProjector):
    """MUTANT 5: Shares a single global pending buffer across multiple accounts."""

    _global_buffer: dict[int, AccountEvent] = {}

    def __init__(self) -> None:
        super().__init__()
        MutantCrossAccountBufferLeak._global_buffer.clear()

    def apply_event(self, event: AccountEvent) -> AccountProjection:
        _base_validate(event)
        aid = event.account_id
        if aid not in self._accounts:
            if event.event_type != EventType.ACCOUNT_OPENED:
                raise AccountNotOpenedError(f"Account {aid} not opened")
            st = _BaseAccountState(account_id=aid, balance=event.amount, last_applied_sequence=1)  # type: ignore[arg-type]
            st.pending_buffer = self._global_buffer
            st.observed_events[1] = event
            self._accounts[aid] = st
            return self._to_projection(st)

        st = self._accounts[aid]
        st.pending_buffer = self._global_buffer

        if event.sequence_id > st.last_applied_sequence + 1:
            self._global_buffer[event.sequence_id] = event
            return self._to_projection(st)

        return super().apply_event(event)


class MutantFrozenBypassOnDrain(BaseProjector):
    """MUTANT 6: Allows buffered deposits to commit after a buffered freeze during drain."""

    def _apply_single_event(self, state: _BaseAccountState, event: AccountEvent) -> None:
        # FLAW: Omits freeze check on deposit during drain
        if event.event_type == EventType.FUNDS_DEPOSITED:
            state.balance += event.amount  # type: ignore[operator]
            state.last_applied_sequence = event.sequence_id
        else:
            super()._apply_single_event(state, event)


class MutantRollbackCommittedOnDrainFail(BaseProjector):
    """MUTANT 7: Erroneously rolls back valid committed event when drain fails."""

    def _execute_and_drain(self, state: _BaseAccountState, event: AccountEvent) -> AccountProjection:
        saved_balance = state.balance
        saved_seq = state.last_applied_sequence
        try:
            return super()._execute_and_drain(state, event)
        except (InsufficientFundsError, AccountFrozenError) as err:
            # FLAW: Rolls back the committed incoming event
            state.balance = saved_balance
            state.last_applied_sequence = saved_seq
            raise err


class MutantBypassBlockedSequence(BaseProjector):
    """MUTANT 8: Continues draining and applies later buffered events after a failure."""

    def _execute_and_drain(self, state: _BaseAccountState, event: AccountEvent) -> AccountProjection:
        self._apply_single_event(state, event)
        state.is_blocked = False
        state.blocked_sequence_id = None

        # FLAW: When an event fails, catches error, blocks, but keeps draining next events!
        for next_seq in sorted(list(state.pending_buffer.keys())):
            next_ev = state.pending_buffer[next_seq]
            try:
                self._apply_single_event(state, next_ev)
                del state.pending_buffer[next_seq]
            except (InsufficientFundsError, AccountFrozenError) as err:
                del state.pending_buffer[next_seq]
                state.is_blocked = True
                state.blocked_sequence_id = next_seq
                # Keeps going! (Bypasses sequence)
        if state.is_blocked:
            raise InsufficientFundsError("Drain failed on some event")
        return self._to_projection(state)


class MutantSilentUnblockedOnFailure(BaseProjector):
    """MUTANT 9: Fails to set is_blocked and blocked_sequence_id on failure."""

    def _execute_and_drain(self, state: _BaseAccountState, event: AccountEvent) -> AccountProjection:
        try:
            self._apply_single_event(state, event)
        except (InsufficientFundsError, AccountFrozenError) as err:
            # FLAW: Fails to set is_blocked and blocked_sequence_id
            raise err

        while (state.last_applied_sequence + 1) in state.pending_buffer:
            next_seq = state.last_applied_sequence + 1
            next_ev = state.pending_buffer[next_seq]
            try:
                self._apply_single_event(state, next_ev)
                del state.pending_buffer[next_seq]
            except (InsufficientFundsError, AccountFrozenError) as err:
                del state.pending_buffer[next_seq]
                # FLAW: Fails to set is_blocked and blocked_sequence_id
                raise err

        return self._to_projection(state)


class MutantFloatPrecision(BaseProjector):
    """MUTANT 10: Converts amounts to float and permits excess decimal precision."""

    def apply_event(self, event: AccountEvent) -> AccountProjection:
        # FLAW: Does not reject excess precision (> 2 decimal places) or float arithmetic
        aid = event.account_id
        if not isinstance(aid, str) or not aid.strip():
            raise EventValidationError("Invalid account_id")

        if aid not in self._accounts:
            if event.event_type != EventType.ACCOUNT_OPENED:
                raise AccountNotOpenedError(f"Account {aid} not opened")
            float_bal = float(event.amount) if event.amount is not None else 0.0  # type: ignore[arg-type]
            st = _BaseAccountState(account_id=aid, balance=float_bal, last_applied_sequence=1)  # type: ignore[arg-type]
            st.observed_events[1] = event
            self._accounts[aid] = st
            return self._to_projection(st)

        return super().apply_event(event)
