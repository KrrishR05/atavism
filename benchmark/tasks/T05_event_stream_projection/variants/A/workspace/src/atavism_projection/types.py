"""Domain types, models, and exceptions for Atavism T05."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class EventType(str, Enum):
    """Supported account event types."""

    ACCOUNT_OPENED = "ACCOUNT_OPENED"
    FUNDS_DEPOSITED = "FUNDS_DEPOSITED"
    FUNDS_WITHDRAWN = "FUNDS_WITHDRAWN"
    ACCOUNT_FROZEN = "ACCOUNT_FROZEN"


@dataclass(frozen=True)
class AccountEvent:
    """Immutable representation of a domain event in the account stream."""

    account_id: str
    event_type: EventType
    sequence_id: int
    amount: Decimal | None = None
    reason: str | None = None


@dataclass(frozen=True)
class AccountProjection:
    """Immutable read-model projection of an account's current state."""

    account_id: str
    balance: Decimal
    is_frozen: bool
    last_applied_sequence: int
    pending_buffer_count: int
    is_blocked: bool
    blocked_sequence_id: int | None


class ProjectionError(Exception):
    """Base exception for all projection domain errors."""


class EventValidationError(ProjectionError):
    """Raised when an event fails schema, precision, or type validation."""


class AccountNotOpenedError(ProjectionError):
    """Raised when an event is received for an account that has not been opened."""


class AccountAlreadyOpenedError(ProjectionError):
    """Raised when an account opening event is received for an already opened account."""


class InsufficientFundsError(ProjectionError):
    """Raised when a withdrawal exceeds available balance."""


class AccountFrozenError(ProjectionError):
    """Raised when a monetary operation is attempted on a frozen account."""


class ConflictingEventError(ProjectionError):
    """Raised when a duplicate sequence ID arrives with a conflicting payload."""


class InvalidEventSequenceError(ProjectionError):
    """Raised when an out-of-order event is received under a FIFO delivery contract."""

