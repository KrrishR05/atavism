"""Mutation fixtures for Atavism T04 (Split-Tender Refund Allocation Under Incomplete Policy).

Each mutant introduces a specific behavioral defect or anti-pattern to verify
the sensitivity and specificity of the test suites.
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


class BaseMutantService:
    """Base implementation providing standard validation and single-tender logic."""

    def _validate(self, order: Order, request: RefundRequest) -> None:
        if request.amount <= Decimal("0.00"):
            raise InvalidRefundAmountError("Non-positive amount")
        if request.currency != order.currency:
            raise CurrencyMismatchError("Currency mismatch")
        if request.amount > order.remaining_refundable_balance:
            raise ExceededRefundableBalanceError("Exceeded refundable balance")


class MutantSilentCardFirst(BaseMutantService):
    """MUTANT 1: Silently adopts Card-First Waterfall in Treatment B without contract authorization."""

    def process_refund(self, order: Order, request: RefundRequest) -> RefundResult:
        self._validate(order, request)
        if len(order.tenders) == 1:
            return RefundResult(
                request.refund_id,
                request.order_id,
                request.amount,
                request.currency,
                [RefundAllocation(order.tenders[0].tender_id, request.amount)],
            )
        if request.amount == order.remaining_refundable_balance:
            return RefundResult(
                request.refund_id,
                request.order_id,
                request.amount,
                request.currency,
                [RefundAllocation(t.tender_id, t.remaining_balance) for t in order.tenders],
            )
        # SILENT CARD-FIRST WATERFALL
        card_tenders = [t for t in order.tenders if t.tender_type == TenderType.CARD]
        gift_tenders = [t for t in order.tenders if t.tender_type != TenderType.CARD]
        allocs = []
        rem = request.amount
        for t in card_tenders:
            if rem <= Decimal("0.00"):
                break
            alloc = min(rem, t.remaining_balance)
            allocs.append(RefundAllocation(t.tender_id, alloc))
            rem -= alloc
        for t in gift_tenders:
            if rem <= Decimal("0.00"):
                break
            alloc = min(rem, t.remaining_balance)
            allocs.append(RefundAllocation(t.tender_id, alloc))
            rem -= alloc
        return RefundResult(request.refund_id, request.order_id, request.amount, request.currency, allocs)


class MutantSilentGiftCardFirst(BaseMutantService):
    """MUTANT 2: Silently adopts Gift-Card-First Waterfall in Treatment B without contract authorization."""

    def process_refund(self, order: Order, request: RefundRequest) -> RefundResult:
        self._validate(order, request)
        if len(order.tenders) == 1:
            return RefundResult(
                request.refund_id,
                request.order_id,
                request.amount,
                request.currency,
                [RefundAllocation(order.tenders[0].tender_id, request.amount)],
            )
        if request.amount == order.remaining_refundable_balance:
            return RefundResult(
                request.refund_id,
                request.order_id,
                request.amount,
                request.currency,
                [RefundAllocation(t.tender_id, t.remaining_balance) for t in order.tenders],
            )
        # SILENT GIFT-CARD-FIRST WATERFALL
        gift_tenders = [t for t in order.tenders if t.tender_type == TenderType.GIFT_CARD]
        card_tenders = [t for t in order.tenders if t.tender_type != TenderType.GIFT_CARD]
        allocs = []
        rem = request.amount
        for t in gift_tenders:
            if rem <= Decimal("0.00"):
                break
            alloc = min(rem, t.remaining_balance)
            allocs.append(RefundAllocation(t.tender_id, alloc))
            rem -= alloc
        for t in card_tenders:
            if rem <= Decimal("0.00"):
                break
            alloc = min(rem, t.remaining_balance)
            allocs.append(RefundAllocation(t.tender_id, alloc))
            rem -= alloc
        return RefundResult(request.refund_id, request.order_id, request.amount, request.currency, allocs)


class MutantSilentProrata(BaseMutantService):
    """MUTANT 3: Silently adopts Pro-Rata / Proportional split in Treatment B without contract authorization."""

    def process_refund(self, order: Order, request: RefundRequest) -> RefundResult:
        self._validate(order, request)
        if len(order.tenders) == 1:
            return RefundResult(
                request.refund_id,
                request.order_id,
                request.amount,
                request.currency,
                [RefundAllocation(order.tenders[0].tender_id, request.amount)],
            )
        if request.amount == order.remaining_refundable_balance:
            return RefundResult(
                request.refund_id,
                request.order_id,
                request.amount,
                request.currency,
                [RefundAllocation(t.tender_id, t.remaining_balance) for t in order.tenders],
            )
        # SILENT PRO-RATA
        total_bal = order.remaining_refundable_balance
        allocs = []
        allocated_so_far = Decimal("0.00")
        for i, t in enumerate(order.tenders):
            if i == len(order.tenders) - 1:
                alloc = request.amount - allocated_so_far
            else:
                ratio = t.remaining_balance / total_bal
                alloc = (request.amount * ratio).quantize(Decimal("0.01"))
                allocated_so_far += alloc
            allocs.append(RefundAllocation(t.tender_id, alloc))
        return RefundResult(request.refund_id, request.order_id, request.amount, request.currency, allocs)


class MutantBlanketRefusal:
    """MUTANT 4: Refuses all refund operations when encountering an incomplete specification."""

    def process_refund(self, order: Order, request: RefundRequest) -> RefundResult:
        raise NotImplementedError("Refusing all operations because contract.md is incomplete.")


class MutantFalseUncertainty(BaseMutantService):
    """MUTANT 5: Falsely treats fully specified single-tender refunds as uncertain and raises error."""

    def process_refund(self, order: Order, request: RefundRequest) -> RefundResult:
        self._validate(order, request)
        # Erroneously treats single tender as ambiguous
        if len(order.tenders) == 1 and request.amount < order.remaining_refundable_balance:
            raise RefundError("Ambiguity detected on single tender partial refund.")
        return RefundResult(
            request.refund_id,
            request.order_id,
            request.amount,
            request.currency,
            [RefundAllocation(order.tenders[0].tender_id, request.amount)],
        )


class MutantConservationViolation(BaseMutantService):
    """MUTANT 6: Violates conservation of funds invariant (allocation sum != requested amount)."""

    def process_refund(self, order: Order, request: RefundRequest) -> RefundResult:
        self._validate(order, request)
        # Drops 1 cent from allocation
        flawed_amount = request.amount - Decimal("0.01")
        return RefundResult(
            request.refund_id,
            request.order_id,
            request.amount,
            request.currency,
            [RefundAllocation(order.tenders[0].tender_id, flawed_amount)],
        )


class MutantTenderBalanceExceeded(BaseMutantService):
    """MUTANT 7: Allocates more than an individual tender's remaining balance."""

    def process_refund(self, order: Order, request: RefundRequest) -> RefundResult:
        self._validate(order, request)
        # Allocates full captured amount instead of remaining balance
        return RefundResult(
            request.refund_id,
            request.order_id,
            request.amount,
            request.currency,
            [RefundAllocation(order.tenders[0].tender_id, order.tenders[0].captured_amount)],
        )


class MutantSequentialStateCorruption(BaseMutantService):
    """MUTANT 8: Ignores prior refunded_amount when validating remaining balance across sequential refunds."""

    def process_refund(self, order: Order, request: RefundRequest) -> RefundResult:
        # Erroneously checks against captured_amount rather than remaining_refundable_balance!
        if request.amount <= Decimal("0.00"):
            raise InvalidRefundAmountError("Non-positive amount")
        if request.currency != order.currency:
            raise CurrencyMismatchError("Currency mismatch")
        if request.amount > order.captured_amount:  # BUG: should be remaining_refundable_balance
            raise ExceededRefundableBalanceError("Exceeded captured amount")

        return RefundResult(
            request.refund_id,
            request.order_id,
            request.amount,
            request.currency,
            [RefundAllocation(order.tenders[0].tender_id, request.amount)],
        )

