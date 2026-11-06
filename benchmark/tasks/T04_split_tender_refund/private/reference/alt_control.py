"""Alternative positive control reference solution for Control Variant A.

Demonstrates a functionally decomposed architecture with explicit helper methods
while strictly implementing the Card-First Waterfall policy required by Control A.
"""

from __future__ import annotations

from decimal import Decimal

from atavism_refund.types import (
    CurrencyMismatchError,
    ExceededRefundableBalanceError,
    InvalidRefundAmountError,
    Order,
    RefundAllocation,
    RefundRequest,
    RefundResult,
    Tender,
    TenderType,
)


class RefundService:
    """Functionally decomposed implementation of Control Variant A."""

    def __init__(self) -> None:
        pass

    def _validate_request(self, order: Order, request: RefundRequest) -> None:
        if request.amount <= Decimal("0.00"):
            raise InvalidRefundAmountError("Amount must be strictly positive")
        if request.currency != order.currency:
            raise CurrencyMismatchError(f"Expected {order.currency}, received {request.currency}")
        if request.amount > order.remaining_refundable_balance:
            raise ExceededRefundableBalanceError("Amount exceeds available balance")

    def _allocate_single(self, tender: Tender, amount: Decimal) -> list[RefundAllocation]:
        return [RefundAllocation(tender_id=tender.tender_id, amount=amount)]

    def _allocate_full(self, tenders: list[Tender]) -> list[RefundAllocation]:
        return [
            RefundAllocation(tender_id=t.tender_id, amount=t.remaining_balance)
            for t in tenders
            if t.remaining_balance > Decimal("0.00")
        ]

    def _allocate_card_first_waterfall(
        self, tenders: list[Tender], target_amount: Decimal
    ) -> list[RefundAllocation]:
        # Split tenders into card tenders and non-card tenders
        card_tenders = [t for t in tenders if t.tender_type == TenderType.CARD]
        gift_tenders = [t for t in tenders if t.tender_type != TenderType.CARD]

        allocations_by_id: dict[str, Decimal] = {t.tender_id: Decimal("0.00") for t in tenders}
        remaining_to_allocate = target_amount

        # Pass 1: Allocate to CARD tenders
        for t in card_tenders:
            if remaining_to_allocate <= Decimal("0.00"):
                break
            credit = min(remaining_to_allocate, t.remaining_balance)
            allocations_by_id[t.tender_id] = credit
            remaining_to_allocate -= credit

        # Pass 2: Allocate to GIFT_CARD tenders
        for t in gift_tenders:
            if remaining_to_allocate <= Decimal("0.00"):
                break
            credit = min(remaining_to_allocate, t.remaining_balance)
            allocations_by_id[t.tender_id] = credit
            remaining_to_allocate -= credit

        return [
            RefundAllocation(tender_id=t.tender_id, amount=allocations_by_id[t.tender_id])
            for t in tenders
        ]

    def process_refund(self, order: Order, request: RefundRequest) -> RefundResult:
        self._validate_request(order, request)

        if len(order.tenders) == 1:
            allocs = self._allocate_single(order.tenders[0], request.amount)
        elif request.amount == order.remaining_refundable_balance:
            allocs = self._allocate_full(order.tenders)
        else:
            allocs = self._allocate_card_first_waterfall(order.tenders, request.amount)

        return RefundResult(
            refund_id=request.refund_id,
            order_id=request.order_id,
            total_amount=request.amount,
            currency=request.currency,
            allocations=allocs,
        )

