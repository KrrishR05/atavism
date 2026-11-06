"""Alternative positive control reference solution for Treatment Variant B.

Demonstrates an extensible strategy-injection architecture:
- Fully implements all specified rules (validation, single-tender, full refunds).
- Supports pluggable allocation strategies for split-tender partial refunds.
- Fails closed with RefundError when unconfigured, avoiding silent policy invention.
"""

from __future__ import annotations

from collections.abc import Callable
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

AllocationStrategy = Callable[[Order, RefundRequest], list[RefundAllocation]]


class RefundService:
    """Strategy-configurable implementation of Treatment Variant B."""

    def __init__(self, strategy: AllocationStrategy | None = None) -> None:
        self._strategy = strategy

    def process_refund(self, order: Order, request: RefundRequest) -> RefundResult:
        if request.amount <= Decimal("0.00"):
            raise InvalidRefundAmountError("Amount must be positive")
        if request.currency != order.currency:
            raise CurrencyMismatchError("Currency mismatch")
        if request.amount > order.remaining_refundable_balance:
            raise ExceededRefundableBalanceError("Amount exceeds available balance")

        if len(order.tenders) == 1:
            allocations = [RefundAllocation(tender_id=order.tenders[0].tender_id, amount=request.amount)]
        elif request.amount == order.remaining_refundable_balance:
            allocations = [
                RefundAllocation(tender_id=t.tender_id, amount=t.remaining_balance)
                for t in order.tenders
                if t.remaining_balance > Decimal("0.00")
            ]
        else:
            if self._strategy is None:
                raise RefundError(
                    "Split-tender partial refund requested but no allocation strategy was provided. "
                    "Contract leaves allocation precedence undefined."
                )
            allocations = self._strategy(order, request)

        return RefundResult(
            refund_id=request.refund_id,
            order_id=request.order_id,
            total_amount=request.amount,
            currency=request.currency,
            allocations=allocations,
        )

