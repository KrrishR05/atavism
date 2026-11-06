"""Diagnostic Category: common_validation.

Verifies input validation invariants required by both Variant A and Variant B:
- Positive amount enforcement (InvalidRefundAmountError)
- Currency consistency (CurrencyMismatchError)
- Remaining balance bounds (ExceededRefundableBalanceError)
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from atavism_refund.service import RefundService
from atavism_refund.types import (
    CurrencyMismatchError,
    ExceededRefundableBalanceError,
    InvalidRefundAmountError,
    Order,
    RefundRequest,
    Tender,
    TenderType,
)


class TestRefundValidation:
    """Tests for mandatory contract validation rules."""

    def test_zero_amount_raises_invalid_amount_error(
        self, service: RefundService, make_tender, make_order, make_request
    ) -> None:
        tender = make_tender("t1", TenderType.CARD, "100.00")
        order = make_order("ord_1", "USD", [tender])
        req = make_request("ref_1", "ord_1", "0.00", "USD")

        with pytest.raises(InvalidRefundAmountError):
            service.process_refund(order, req)

    def test_negative_amount_raises_invalid_amount_error(
        self, service: RefundService, make_tender, make_order, make_request
    ) -> None:
        tender = make_tender("t1", TenderType.CARD, "100.00")
        order = make_order("ord_1", "USD", [tender])
        req = make_request("ref_1", "ord_1", "-15.50", "USD")

        with pytest.raises(InvalidRefundAmountError):
            service.process_refund(order, req)

    def test_currency_mismatch_raises_error(
        self, service: RefundService, make_tender, make_order, make_request
    ) -> None:
        tender = make_tender("t1", TenderType.CARD, "50.00")
        order = make_order("ord_1", "USD", [tender])
        req = make_request("ref_1", "ord_1", "25.00", "EUR")

        with pytest.raises(CurrencyMismatchError):
            service.process_refund(order, req)

    def test_amount_exceeding_total_captured_raises_error(
        self, service: RefundService, make_tender, make_order, make_request
    ) -> None:
        tender = make_tender("t1", TenderType.CARD, "50.00")
        order = make_order("ord_1", "USD", [tender])
        req = make_request("ref_1", "ord_1", "50.01", "USD")

        with pytest.raises(ExceededRefundableBalanceError):
            service.process_refund(order, req)

    def test_amount_exceeding_remaining_balance_after_prior_refund_raises_error(
        self, service: RefundService, make_tender, make_order, make_request
    ) -> None:
        tender = make_tender("t1", TenderType.CARD, "100.00", "60.00")  # remaining is 40.00
        order = make_order("ord_1", "USD", [tender])
        req = make_request("ref_1", "ord_1", "40.01", "USD")

        with pytest.raises(ExceededRefundableBalanceError):
            service.process_refund(order, req)

    def test_exact_remaining_balance_is_allowed(
        self, service: RefundService, make_tender, make_order, make_request
    ) -> None:
        tender = make_tender("t1", TenderType.CARD, "100.00", "40.00")  # remaining 60.00
        order = make_order("ord_1", "USD", [tender])
        req = make_request("ref_1", "ord_1", "60.00", "USD")

        result = service.process_refund(order, req)
        assert result.total_amount == Decimal("60.00")

