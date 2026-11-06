"""Account projector service stub."""

from __future__ import annotations

from atavism_projection.types import (
    AccountAlreadyOpenedError,
    AccountEvent,
    AccountFrozenError,
    AccountNotOpenedError,
    AccountProjection,
    ConflictingEventError,
    EventValidationError,
    InsufficientFundsError,
    InvalidEventSequenceError,
    ProjectionError,
)


class AccountProjector:
    """Maintains state projections for financial accounts from an event stream."""

    def __init__(self) -> None:
        pass

    def apply_event(self, event: AccountEvent) -> AccountProjection:
        """Applies an incoming event and returns the updated account projection.

        Returns:
            AccountProjection with updated balance, last_applied_sequence,
            is_frozen, pending_buffer_count, is_blocked, and blocked_sequence_id.

        Raises:
            EventValidationError: If event payload, sequence, or precision is invalid.
            AccountNotOpenedError: If account has not been opened.
            AccountAlreadyOpenedError: If reopening an existing account.
            InsufficientFundsError: If withdrawal exceeds available balance.
            AccountFrozenError: If monetary operation attempted on frozen account.
            ConflictingEventError: If sequence ID has a conflicting payload.
            InvalidEventSequenceError: If sequence gap encountered under FIFO contract.
        """
        raise NotImplementedError("AccountProjector.apply_event is not implemented")

    def get_projection(self, account_id: str) -> AccountProjection | None:
        """Returns the current projection for an account, or None if not opened.

        When an account stream is blocked due to a domain precondition failure,
        the returned projection reflects is_blocked == True and blocked_sequence_id
        identifying the failed sequence number. When operating normally or unblocked,
        is_blocked == False and blocked_sequence_id is None.
        """
        raise NotImplementedError(
            "AccountProjector.get_projection is not implemented"
        )

