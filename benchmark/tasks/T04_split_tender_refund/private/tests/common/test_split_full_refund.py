"""Diagnostic Category: common_split_full_refund.

Verifies deterministic full refund operations for split-tender orders required
by both Variant A and Variant B:
- Each tender receives exactly its remaining refundable balance.
"""

from __future__ import annotations

from decimal import Decimal

from atavism_refund.service import RefundService
from atavism_refund.types import TenderType


class TestSplitTenderFullRefund:
    """Tests for split-tender full refund rules."""

    def test_split_card_and_gift_card_full_refund(
        self, service: RefundService, make_tender, make_order, make_request
    ) -> None:
        t_card = make_tender("t_card", TenderType.CARD, "70.00")
        t_gc = make_tender("t_gc", TenderType.GIFT_CARD, "30.00")
        order = make_order("ord_201", "USD", [t_card, t_gc])
        req = make_request("ref_201", "ord_201", "100.00", "USD")

        result = service.process_refund(order, req)

        assert result.total_amount == Decimal("100.00")
        alloc_map = {a.tender_id: a.amount for a in result.allocations}
        assert alloc_map["t_card"] == Decimal("70.00")
        assert alloc_map["t_gc"] == Decimal("30.00")

    def test_split_multiple_cards_and_gift_card_full_refund(
        self, service: RefundService, make_tender, make_order, make_request
    ) -> None:
        t_card1 = make_tender("t_c1", TenderType.CARD, "50.00")
        t_card2 = make_tender("t_c2", TenderType.CARD, "30.00")
        t_gc = make_tender("t_gc", TenderType.GIFT_CARD, "20.00")
        order = make_order("ord_202", "USD", [t_card1, t_card2, t_gc])
        req = make_request("ref_202", "ord_202", "100.00", "USD")

        result = service.process_refund(order, req)

        assert result.total_amount == Decimal("100.00")
        alloc_map = {a.tender_id: a.amount for a in result.allocations}
        assert alloc_map["t_c1"] == Decimal("50.00")
        assert alloc_map["t_c2"] == Decimal("30.00")
        assert alloc_map["t_gc"] == Decimal("20.00")

    def test_split_full_refund_with_prior_partial_refunds(
        self, service: RefundService, make_tender, make_order, make_request
    ) -> None:
        # Card 80 captured, 30 refunded -> 50 remaining
        # GC 20 captured, 5 refunded -> 15 remaining
        # Total remaining = 65.00
        t_card = make_tender("t_card", TenderType.CARD, "80.00", "30.00")
        t_gc = make_tender("t_gc", TenderType.GIFT_CARD, "20.00", "5.00")
        order = make_order("ord_203", "USD", [t_card, t_gc])
        req = make_request("ref_203", "ord_203", "65.00", "USD")

        result = service.process_refund(order, req)

        assert result.total_amount == Decimal("65.00")
        alloc_map = {a.tender_id: a.amount for a in result.allocations}
        assert alloc_map["t_card"] == Decimal("50.00")
        assert alloc_map["t_gc"] == Decimal("15.00")

