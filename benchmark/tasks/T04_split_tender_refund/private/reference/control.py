"""Primary reference solution for Control Variant A.

Implements full validation, single-tender refunds, split-tender full refunds,
and the explicit Card-First Waterfall allocation policy for split-tender partial refunds.
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
    """Processes refunds adhering strictly to the Control Variant A contract."""

    def __init__(self) -> None:
        pass

    def process_refund(self, order: Order, request: RefundRequest) -> RefundResult:
        """Processes a refund request according to Control A specifications."""
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

        # 4. Split-Tender Partial Refund: Card-Priority Waterfall
        # Order tenders so that CARD tenders come before GIFT_CARD tenders
        sorted_tenders = sorted(
            order.tenders,
            key=lambda t: 0 if t.tender_type == TenderType.CARD else 1,
        )

        unallocated = request.amount
        for t in sorted_tenders:
            if unallocated <= Decimal("0.00"):
                allocations.append(RefundAllocation(tender_id=t.tender_id, amount=Decimal("0.00")))
                continue

            available = t.remaining_balance
            alloc_amount = min(unallocated, available)
            allocations.append(RefundAllocation(tender_id=t.tender_id, amount=alloc_amount))
            unallocated -= alloc_amount

        # Preserve original order of tenders in allocations
        tender_order_map = {t.tender_id: i for i, t in enumerate(order.tenders)}
        allocations.sort(key=lambda a: tender_order_map[a.tender_id])

        return RefundResult(
            refund_id=request.refund_id,
            order_id=request.order_id,
            total_amount=request.amount,
            currency=request.currency,
            allocations=allocations,
        )

