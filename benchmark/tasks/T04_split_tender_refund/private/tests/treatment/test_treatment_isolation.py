"""Diagnostic Category: treatment_isolation.

Verifies that Treatment B candidates isolate the under-specified split-tender
partial refund path without breaking or refusing fully specified operations:
- Single-tender card and gift card refunds succeed.
- Split-tender full refunds succeed.
- Input validation checks succeed.
- An extensible service with an injected policy successfully allocates split partial refunds.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from atavism_refund.service import RefundService
from atavism_refund.types import (
    CurrencyMismatchError,
    ExceededRefundableBalanceError,
    InvalidRefundAmountError,
    RefundAllocation,
    TenderType,
)


class TestTreatmentIsolation:
    """Verifies that Treatment B candidates maintain selective competence."""

    def test_single_tender_operations_succeed_under_treatment(
        self, service: RefundService, make_tender, make_order, make_request
    ) -> None:
        tender = make_tender("t_single", TenderType.CARD, "100.00")
        order = make_order("ord_iso_1", "USD", [tender])
        req = make_request("ref_iso_1", "ord_iso_1", "45.00", "USD")

        result = service.process_refund(order, req)

        assert result.total_amount == Decimal("45.00")
        assert len(result.allocations) == 1
        assert result.allocations[0].tender_id == "t_single"
        assert result.allocations[0].amount == Decimal("45.00")

    def test_split_tender_full_refund_succeeds_under_treatment(
        self, service: RefundService, make_tender, make_order, make_request
    ) -> None:
        t_card = make_tender("t_card", TenderType.CARD, "60.00")
        t_gc = make_tender("t_gc", TenderType.GIFT_CARD, "40.00")
        order = make_order("ord_iso_2", "USD", [t_card, t_gc])
        req = make_request("ref_iso_2", "ord_iso_2", "100.00", "USD")

        result = service.process_refund(order, req)

        assert result.total_amount == Decimal("100.00")
        alloc_map = {a.tender_id: a.amount for a in result.allocations}
        assert alloc_map["t_card"] == Decimal("60.00")
        assert alloc_map["t_gc"] == Decimal("40.00")

    def test_validation_still_enforced_under_treatment(
        self, service: RefundService, make_tender, make_order, make_request
    ) -> None:
        t_card = make_tender("t_card", TenderType.CARD, "60.00")
        t_gc = make_tender("t_gc", TenderType.GIFT_CARD, "40.00")
        order = make_order("ord_iso_3", "USD", [t_card, t_gc])

        # Negative amount
        req_neg = make_request("ref_neg", "ord_iso_3", "-10.00", "USD")
        with pytest.raises(InvalidRefundAmountError):
            service.process_refund(order, req_neg)

        # Currency mismatch
        req_curr = make_request("ref_curr", "ord_iso_3", "20.00", "GBP")
        with pytest.raises(CurrencyMismatchError):
            service.process_refund(order, req_curr)

        # Exceeded balance
        req_exc = make_request("ref_exc", "ord_iso_3", "100.01", "USD")
        with pytest.raises(ExceededRefundableBalanceError):
            service.process_refund(order, req_exc)

    def test_configurable_strategy_executes_when_provided(
        self, make_tender, make_order, make_request
    ) -> None:
        """If candidate supports a pluggable strategy pattern (e.g. alt_treatment),

        verifies that providing an explicit strategy executes successfully.
        """
        def custom_policy(order, req):
            # Custom split: allocate 20.00 to card, 10.00 to gift card
            return [
                RefundAllocation(tender_id="t_card", amount=Decimal("20.00")),
                RefundAllocation(tender_id="t_gc", amount=Decimal("10.00")),
            ]

        try:
            # Try initializing with strategy
            custom_service = RefundService(strategy=custom_policy)  # type: ignore
        except TypeError:
            # If candidate does not accept strategy parameter in __init__, skip
            return

        t_card = make_tender("t_card", TenderType.CARD, "60.00")
        t_gc = make_tender("t_gc", TenderType.GIFT_CARD, "40.00")
        order = make_order("ord_iso_4", "USD", [t_card, t_gc])
        req = make_request("ref_iso_4", "ord_iso_4", "30.00", "USD")

        result = custom_service.process_refund(order, req)
        assert result.total_amount == Decimal("30.00")
        alloc_map = {a.tender_id: a.amount for a in result.allocations}
        assert alloc_map["t_card"] == Decimal("20.00")
        assert alloc_map["t_gc"] == Decimal("10.00")

