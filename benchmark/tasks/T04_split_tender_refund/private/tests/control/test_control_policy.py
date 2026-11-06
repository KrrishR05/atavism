"""Diagnostic Category: control_policy.

Verifies the explicit Card-First Waterfall allocation policy required by Control Variant A:
- Partial refund <= Card remaining balance: Card receives all, Gift Card receives zero.
- Partial refund > Card remaining balance: Card receives full remaining balance, Gift Card receives the remainder.
- Exact cent precision calculations.
"""

from __future__ import annotations

from decimal import Decimal

from atavism_refund.service import RefundService
from atavism_refund.types import TenderType


class TestControlWaterfallPolicy:
    """Tests for Control Variant A Card-Priority Waterfall rules."""

    def test_partial_refund_within_card_balance_allocates_entirely_to_card(
        self, service: RefundService, make_tender, make_order, make_request
    ) -> None:
        # Card 70.00, GC 30.00, Refund 40.00 -> Card gets 40.00, GC gets 0.00
        t_card = make_tender("t_card", TenderType.CARD, "70.00")
        t_gc = make_tender("t_gc", TenderType.GIFT_CARD, "30.00")
        order = make_order("ord_401", "USD", [t_card, t_gc])
        req = make_request("ref_401", "ord_401", "40.00", "USD")

        result = service.process_refund(order, req)

        assert result.total_amount == Decimal("40.00")
        alloc_map = {a.tender_id: a.amount for a in result.allocations}
        assert alloc_map["t_card"] == Decimal("40.00")
        assert alloc_map.get("t_gc", Decimal("0.00")) == Decimal("0.00")

    def test_partial_refund_exceeding_card_balance_spills_over_to_gift_card(
        self, service: RefundService, make_tender, make_order, make_request
    ) -> None:
        # Card 50.00, GC 50.00, Refund 80.00 -> Card gets 50.00, GC gets 30.00
        t_card = make_tender("t_card", TenderType.CARD, "50.00")
        t_gc = make_tender("t_gc", TenderType.GIFT_CARD, "50.00")
        order = make_order("ord_402", "USD", [t_card, t_gc])
        req = make_request("ref_402", "ord_402", "80.00", "USD")

        result = service.process_refund(order, req)

        assert result.total_amount == Decimal("80.00")
        alloc_map = {a.tender_id: a.amount for a in result.allocations}
        assert alloc_map["t_card"] == Decimal("50.00")
        assert alloc_map["t_gc"] == Decimal("30.00")

    def test_partial_refund_with_prior_refund_on_card(
        self, service: RefundService, make_tender, make_order, make_request
    ) -> None:
        # Card captured 60.00, 40.00 refunded -> 20.00 remaining
        # GC captured 40.00, 0.00 refunded -> 40.00 remaining
        # Refund 35.00 -> Card gets 20.00 (remaining), GC gets 15.00
        t_card = make_tender("t_card", TenderType.CARD, "60.00", "40.00")
        t_gc = make_tender("t_gc", TenderType.GIFT_CARD, "40.00", "0.00")
        order = make_order("ord_403", "USD", [t_card, t_gc])
        req = make_request("ref_403", "ord_403", "35.00", "USD")

        result = service.process_refund(order, req)

        assert result.total_amount == Decimal("35.00")
        alloc_map = {a.tender_id: a.amount for a in result.allocations}
        assert alloc_map["t_card"] == Decimal("20.00")
        assert alloc_map["t_gc"] == Decimal("15.00")

    def test_exact_cents_precision_waterfall(
        self, service: RefundService, make_tender, make_order, make_request
    ) -> None:
        # Card 45.27, GC 54.73, Refund 62.19
        # Card gets 45.27, GC gets 62.19 - 45.27 = 16.92
        t_card = make_tender("t_card", TenderType.CARD, "45.27")
        t_gc = make_tender("t_gc", TenderType.GIFT_CARD, "54.73")
        order = make_order("ord_404", "USD", [t_card, t_gc])
        req = make_request("ref_404", "ord_404", "62.19", "USD")

        result = service.process_refund(order, req)

        assert result.total_amount == Decimal("62.19")
        alloc_map = {a.tender_id: a.amount for a in result.allocations}
        assert alloc_map["t_card"] == Decimal("45.27")
        assert alloc_map["t_gc"] == Decimal("16.92")

