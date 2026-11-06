"""Domain models, data structures, and exceptions for refund processing."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class TenderType(str, Enum):
    """Supported payment tender types."""
    CARD = "CARD"
    GIFT_CARD = "GIFT_CARD"


@dataclass(frozen=True)
class Tender:
    """An individual payment tender captured on an order."""
    tender_id: str
    tender_type: TenderType
    captured_amount: Decimal
    refunded_amount: Decimal = Decimal("0.00")

    @property
    def remaining_balance(self) -> Decimal:
        """Remaining balance available for refunds on this tender."""
        return self.captured_amount - self.refunded_amount


@dataclass(frozen=True)
class Order:
    """A customer order funded by one or more payment tenders."""
    order_id: str
    currency: str
    tenders: list[Tender]

    @property
    def captured_amount(self) -> Decimal:
        """Total original amount captured across all tenders."""
        return sum((t.captured_amount for t in self.tenders), Decimal("0.00"))

    @property
    def remaining_refundable_balance(self) -> Decimal:
        """Total balance remaining across all tenders eligible for refund."""
        return sum((t.remaining_balance for t in self.tenders), Decimal("0.00"))


@dataclass(frozen=True)
class RefundRequest:
    """A request to refund an amount against an order."""
    refund_id: str
    order_id: str
    amount: Decimal
    currency: str


@dataclass(frozen=True)
class RefundAllocation:
    """Amount allocated to a specific tender within a refund operation."""
    tender_id: str
    amount: Decimal


@dataclass(frozen=True)
class RefundResult:
    """Result of a processed refund operation."""
    refund_id: str
    order_id: str
    total_amount: Decimal
    currency: str
    allocations: list[RefundAllocation]


class RefundError(Exception):
    """Base exception for refund processing errors."""


class InvalidRefundAmountError(RefundError):
    """Raised when the requested refund amount is non-positive."""


class CurrencyMismatchError(RefundError):
    """Raised when the refund request currency does not match the order currency."""


class ExceededRefundableBalanceError(RefundError):
    """Raised when the refund amount exceeds the remaining refundable balance."""

