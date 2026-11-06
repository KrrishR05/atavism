"""Diagnostic Category: common_integrity.

Verifies state invariants, conservation of funds, input immutability,
and sequential refund balance constraints across all variants:
- sum(allocations) == request.amount
- 0 <= allocation <= tender.remaining_balance
- original objects are never mutated in place
- sequential refunds respect accumulated balances
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from atavism_refund.service import RefundService
from atavism_refund.types import (
    ExceededRefundableBalanceError,
    Tender,
    TenderType,
)


class TestStateIntegrityAndInvariants:
    """Tests for fundamental domain invariants."""

    def test_allocation_sum_matches_request_amount_on_single_tender(
        self, service: RefundService, make_tender, make_order, make_request
    ) -> None:
        tender = make_tender("t1", TenderType.CARD, "100.00")
        order = make_order("ord_301", "USD", [tender])
        req = make_request("ref_301", "ord_301", "42.50", "USD")

        result = service.process_refund(order, req)

        total_allocated = sum((a.amount for a in result.allocations), Decimal("0.00"))
        assert total_allocated == req.amount
        assert total_allocated == Decimal("42.50")

    def test_allocation_sum_matches_request_amount_on_split_full(
        self, service: RefundService, make_tender, make_order, make_request
    ) -> None:
        t1 = make_tender("t1", TenderType.CARD, "60.00")
        t2 = make_tender("t2", TenderType.GIFT_CARD, "40.00")
        order = make_order("ord_302", "USD", [t1, t2])
        req = make_request("ref_302", "ord_302", "100.00", "USD")

        result = service.process_refund(order, req)

        total_allocated = sum((a.amount for a in result.allocations), Decimal("0.00"))
        assert total_allocated == Decimal("100.00")

    def test_allocations_never_exceed_individual_tender_remaining_balance(
        self, service: RefundService, make_tender, make_order, make_request
    ) -> None:
        t1 = make_tender("t1", TenderType.CARD, "50.00", "20.00")  # remaining 30.00
        order = make_order("ord_303", "USD", [t1])
        req = make_request("ref_303", "ord_303", "30.00", "USD")

        result = service.process_refund(order, req)

        for a in result.allocations:
            assert a.amount <= t1.remaining_balance
            assert a.amount >= Decimal("0.00")

    def test_original_input_objects_are_not_mutated_in_place(
        self, service: RefundService, make_tender, make_order, make_request
    ) -> None:
        tender = make_tender("t1", TenderType.CARD, "100.00", "0.00")
        order = make_order("ord_304", "USD", [tender])
        req = make_request("ref_304", "ord_304", "30.00", "USD")

        # Snapshot pre-execution values
        orig_captured = tender.captured_amount
        orig_refunded = tender.refunded_amount
        orig_req_amount = req.amount

        service.process_refund(order, req)

        assert tender.captured_amount == orig_captured
        assert tender.refunded_amount == orig_refunded
        assert req.amount == orig_req_amount

    def test_sequential_refunds_respect_accumulated_balances(
        self, service: RefundService, make_tender, make_order, make_request
    ) -> None:
        # Initial capture 100.00
        tender = make_tender("t1", TenderType.CARD, "100.00", "0.00")
        order1 = make_order("ord_305", "USD", [tender])
        req1 = make_request("ref_305_a", "ord_305", "40.00", "USD")

        res1 = service.process_refund(order1, req1)
        assert res1.total_amount == Decimal("40.00")

        # Subsequent refund state simulation: tender now has 40.00 refunded
        updated_tender = make_tender("t1", TenderType.CARD, "100.00", "40.00")
        order2 = make_order("ord_305", "USD", [updated_tender])

        # Second valid refund of 50.00 (remaining is 60.00)
        req2 = make_request("ref_305_b", "ord_305", "50.00", "USD")
        res2 = service.process_refund(order2, req2)
        assert res2.total_amount == Decimal("50.00")

        # Third refund of 15.00 should fail because only 10.00 remaining
        updated_tender2 = make_tender("t1", TenderType.CARD, "100.00", "90.00")
        order3 = make_order("ord_305", "USD", [updated_tender2])
        req3 = make_request("ref_305_c", "ord_305", "15.00", "USD")

        with pytest.raises(ExceededRefundableBalanceError):
            service.process_refund(order3, req3)

