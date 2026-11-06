"""Diagnostic Category: common_single_tender.

Verifies deterministic single-tender refund operations required by both Variant A and Variant B:
- Single Card full refund
- Single Card partial refund
- Single Gift Card full refund
- Single Gift Card partial refund
- Single tender with non-zero initial refunded_amount
"""

from __future__ import annotations

from decimal import Decimal

from atavism_refund.service import RefundService
from atavism_refund.types import TenderType


class TestSingleTenderRefunds:
    """Tests for single-tender refund rules."""

    def test_single_card_full_refund(
        self, service: RefundService, make_tender, make_order, make_request
    ) -> None:
        tender = make_tender("t_card_1", TenderType.CARD, "120.50")
        order = make_order("ord_101", "USD", [tender])
        req = make_request("ref_101", "ord_101", "120.50", "USD")

        result = service.process_refund(order, req)

        assert result.refund_id == "ref_101"
        assert result.order_id == "ord_101"
        assert result.total_amount == Decimal("120.50")
        assert result.currency == "USD"
        assert len(result.allocations) == 1
        assert result.allocations[0].tender_id == "t_card_1"
        assert result.allocations[0].amount == Decimal("120.50")

    def test_single_card_partial_refund(
        self, service: RefundService, make_tender, make_order, make_request
    ) -> None:
        tender = make_tender("t_card_1", TenderType.CARD, "100.00")
        order = make_order("ord_102", "USD", [tender])
        req = make_request("ref_102", "ord_102", "35.25", "USD")

        result = service.process_refund(order, req)

        assert result.total_amount == Decimal("35.25")
        assert len(result.allocations) == 1
        assert result.allocations[0].tender_id == "t_card_1"
        assert result.allocations[0].amount == Decimal("35.25")

    def test_single_gift_card_full_refund(
        self, service: RefundService, make_tender, make_order, make_request
    ) -> None:
        tender = make_tender("t_gc_1", TenderType.GIFT_CARD, "50.00")
        order = make_order("ord_103", "USD", [tender])
        req = make_request("ref_103", "ord_103", "50.00", "USD")

        result = service.process_refund(order, req)

        assert result.total_amount == Decimal("50.00")
        assert len(result.allocations) == 1
        assert result.allocations[0].tender_id == "t_gc_1"
        assert result.allocations[0].amount == Decimal("50.00")

    def test_single_gift_card_partial_refund(
        self, service: RefundService, make_tender, make_order, make_request
    ) -> None:
        tender = make_tender("t_gc_1", TenderType.GIFT_CARD, "75.00")
        order = make_order("ord_104", "USD", [tender])
        req = make_request("ref_104", "ord_104", "22.50", "USD")

        result = service.process_refund(order, req)

        assert result.total_amount == Decimal("22.50")
        assert len(result.allocations) == 1
        assert result.allocations[0].tender_id == "t_gc_1"
        assert result.allocations[0].amount == Decimal("22.50")

    def test_single_tender_with_prior_refunds_partial(
        self, service: RefundService, make_tender, make_order, make_request
    ) -> None:
        # 100.00 captured, 40.00 already refunded -> 60.00 remaining
        tender = make_tender("t_card_1", TenderType.CARD, "100.00", "40.00")
        order = make_order("ord_105", "USD", [tender])
        req = make_request("ref_105", "ord_105", "30.00", "USD")

        result = service.process_refund(order, req)

        assert result.total_amount == Decimal("30.00")
        assert len(result.allocations) == 1
        assert result.allocations[0].tender_id == "t_card_1"
        assert result.allocations[0].amount == Decimal("30.00")

