"""Shared pytest fixtures for Atavism T04 refund tests."""

from __future__ import annotations

from decimal import Decimal

import pytest
from atavism_refund.service import RefundService
from atavism_refund.types import (
    Order,
    RefundRequest,
    Tender,
    TenderType,
)


@pytest.fixture
def service() -> RefundService:
    """Provides a fresh instance of RefundService."""
    return RefundService()


@pytest.fixture
def make_tender():
    """Factory fixture for creating Tender instances."""
    def _make(
        tender_id: str,
        tender_type: TenderType,
        captured_amount: str | Decimal,
        refunded_amount: str | Decimal = "0.00",
    ) -> Tender:
        return Tender(
            tender_id=tender_id,
            tender_type=tender_type,
            captured_amount=Decimal(str(captured_amount)),
            refunded_amount=Decimal(str(refunded_amount)),
        )
    return _make


@pytest.fixture
def make_order():
    """Factory fixture for creating Order instances."""
    def _make(order_id: str, currency: str, tenders: list[Tender]) -> Order:
        return Order(
            order_id=order_id,
            currency=currency,
            tenders=tenders,
        )
    return _make


@pytest.fixture
def make_request():
    """Factory fixture for creating RefundRequest instances."""
    def _make(refund_id: str, order_id: str, amount: str | Decimal, currency: str) -> RefundRequest:
        return RefundRequest(
            refund_id=refund_id,
            order_id=order_id,
            amount=Decimal(str(amount)),
            currency=currency,
        )
    return _make

