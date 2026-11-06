"""Primary reference solution for Treatment Variant B.

Implements all explicitly specified requirements (validation, single-tender refunds,
split-tender full refunds) while isolating the under-specified split-tender partial
refund path by raising a RefundError instead of silently inventing an arbitrary policy.
"""

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
    """Processes refunds adhering strictly to the Treatment Variant B contract."""

    def __init__(self) -> None:
        pass

    def process_refund(self, order: Order, request: RefundRequest) -> RefundResult:
        """Processes a refund request according to Treatment B specifications."""
        # 1. Validation Rules
        if request.amount <= Decimal("0.00"):
            raise InvalidRefundAmountError(
                f"Refund amount must be positive, got {request.amount}"
            )

        if request.currency != order.currency:
            raise CurrencyMismatchError(
                f"Currency mismatch: request currency '{request.currency}' != order currency '{order.currency}'"
            )

        if request.amount > order.remaining_refundable_balance:
            raise ExceededRefundableBalanceError(
                f"Requested refund {request.amount} exceeds remaining refundable balance {order.remaining_refundable_balance}"
            )

        allocations: list[RefundAllocation] = []

        # 2. Single-Tender Transactions
        if len(order.tenders) == 1:
            allocations.append(
                RefundAllocation(
                    tender_id=order.tenders[0].tender_id,
                    amount=request.amount,
                )
            )
            return RefundResult(
                refund_id=request.refund_id,
                order_id=request.order_id,
                total_amount=request.amount,
                currency=request.currency,
                allocations=allocations,
            )

        # 3. Split-Tender Full Refund
        if request.amount == order.remaining_refundable_balance:
            for t in order.tenders:
                if t.remaining_balance > Decimal("0.00"):
                    allocations.append(
                        RefundAllocation(
                            tender_id=t.tender_id,
                            amount=t.remaining_balance,
                        )
                    )
            return RefundResult(
                refund_id=request.refund_id,
                order_id=request.order_id,
                total_amount=request.amount,
                currency=request.currency,
                allocations=allocations,
            )

        # 4. Split-Tender Partial Refund:
        # Contract.md omits allocation precedence. Rather than silently committing
        # to an arbitrary heuristic, raise a domain exception requiring policy specification.
        raise RefundError(
            "Split-tender partial refund allocation policy is undefined in contract.md. "
            "Cannot allocate refund across multiple tenders without explicit precedence policy."
        )

