"""Refund processing service stub."""

from __future__ import annotations

from decimal import Decimal

from atavism_refund.types import (
    CurrencyMismatchError,
    ExceededRefundableBalanceError,
    InvalidRefundAmountError,
    Order,
    RefundAllocation,
    RefundError,
    RefundRequest,
    RefundResult,
    Tender,
    TenderType,
)


class RefundService:
    """Processes refund requests for captured orders in accordance with contract.md."""

    def __init__(self) -> None:
        pass

    def process_refund(self, order: Order, request: RefundRequest) -> RefundResult:
        """Processes a refund request against the specified order."""
        raise NotImplementedError("RefundService.process_refund is not implemented")

