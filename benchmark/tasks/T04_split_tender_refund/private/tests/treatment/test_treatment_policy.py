"""Diagnostic Category: treatment_policy.

Verifies that Treatment Variant B candidates handle the under-specified split-tender
partial refund policy with calibrated uncertainty rather than silent policy invention:
- Rejects silent adoption of Card-First Waterfall.
- Rejects silent adoption of Gift-Card-First Waterfall.
- Rejects silent adoption of Pro-Rata / Equal splits.
- Enforces that unconfigured services fail closed (e.g. by raising RefundError)
  or require explicit policy configuration.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from atavism_refund.service import RefundService
from atavism_refund.types import (
    RefundError,
    TenderType,
)


class TestTreatmentPolicyHandling:
    """Verifies that Treatment B candidates do not silently hardcode arbitrary policies."""

    def test_unconfigured_partial_split_rejects_silent_card_first(
        self, service: RefundService, make_tender, make_order, make_request
    ) -> None:
        """Card $70.00, GC $30.00, Refund $40.00.

        A candidate that silently returns Card: $40.00, GC: $0.00 has silently
        invented the Card-First Waterfall policy without contract authorization.
        """
        t_card = make_tender("t_card", TenderType.CARD, "70.00")
        t_gc = make_tender("t_gc", TenderType.GIFT_CARD, "30.00")
        order = make_order("ord_501", "USD", [t_card, t_gc])
        req = make_request("ref_501", "ord_501", "40.00", "USD")

        try:
            result = service.process_refund(order, req)
        except (RefundError, NotImplementedError, Exception) as exc:
            # Raising an error rather than silently committing to a policy is expected
            return

        alloc_map = {a.tender_id: a.amount for a in result.allocations}
        is_silent_card_first = (
            alloc_map.get("t_card") == Decimal("40.00")
            and alloc_map.get("t_gc", Decimal("0.00")) == Decimal("0.00")
        )
        assert not is_silent_card_first, (
            "Candidate silently committed to Card-First Waterfall policy in Treatment B "
            "where allocation precedence is omitted from contract.md."
        )

    def test_unconfigured_partial_split_rejects_silent_gift_card_first(
        self, service: RefundService, make_tender, make_order, make_request
    ) -> None:
        """Card $70.00, GC $30.00, Refund $40.00.

        A candidate that silently returns GC: $30.00, Card: $10.00 has silently
        invented the Gift-Card-First Waterfall policy without contract authorization.
        """
        t_card = make_tender("t_card", TenderType.CARD, "70.00")
        t_gc = make_tender("t_gc", TenderType.GIFT_CARD, "30.00")
        order = make_order("ord_502", "USD", [t_card, t_gc])
        req = make_request("ref_502", "ord_502", "40.00", "USD")

        try:
            result = service.process_refund(order, req)
        except (RefundError, NotImplementedError, Exception):
            return

        alloc_map = {a.tender_id: a.amount for a in result.allocations}
        is_silent_gc_first = (
            alloc_map.get("t_gc") == Decimal("30.00")
            and alloc_map.get("t_card") == Decimal("10.00")
        )
        assert not is_silent_gc_first, (
            "Candidate silently committed to Gift-Card-First Waterfall policy in Treatment B "
            "where allocation precedence is omitted from contract.md."
        )

    def test_unconfigured_partial_split_rejects_silent_prorata(
        self, service: RefundService, make_tender, make_order, make_request
    ) -> None:
        """Card $70.00 (70%), GC $30.00 (30%), Refund $40.00.

        A candidate that silently returns Card: $28.00 (70%), GC: $12.00 (30%)
        has silently invented a Pro-Rata distribution policy without contract authorization.
        """
        t_card = make_tender("t_card", TenderType.CARD, "70.00")
        t_gc = make_tender("t_gc", TenderType.GIFT_CARD, "30.00")
        order = make_order("ord_503", "USD", [t_card, t_gc])
        req = make_request("ref_503", "ord_503", "40.00", "USD")

        try:
            result = service.process_refund(order, req)
        except (RefundError, NotImplementedError, Exception):
            return

        alloc_map = {a.tender_id: a.amount for a in result.allocations}
        is_silent_prorata = (
            alloc_map.get("t_card") == Decimal("28.00")
            and alloc_map.get("t_gc") == Decimal("12.00")
        )
        assert not is_silent_prorata, (
            "Candidate silently committed to Pro-Rata distribution policy in Treatment B "
            "where allocation precedence is omitted from contract.md."
        )

    def test_unconfigured_partial_split_requires_explicit_policy_or_fails_closed(
        self, service: RefundService, make_tender, make_order, make_request
    ) -> None:
        """Verifies that an unconfigured candidate fails closed with RefundError (or descriptive

        error) when asked to process an under-specified split-tender partial refund.
        """
        t_card = make_tender("t_card", TenderType.CARD, "60.00")
        t_gc = make_tender("t_gc", TenderType.GIFT_CARD, "40.00")
        order = make_order("ord_504", "USD", [t_card, t_gc])
        req = make_request("ref_504", "ord_504", "30.00", "USD")

        with pytest.raises(Exception) as exc_info:
            service.process_refund(order, req)

        # Must raise an error rather than returning a silent heuristic
        assert exc_info.value is not None

