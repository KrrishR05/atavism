# Atavism Task T04: E-Commerce Refund Service

## Objective
Implement the `RefundService` class in `src/atavism_refund/service.py` to process refund requests against captured customer orders.

## Requirements
1. Review `contract.md` for domain rules, validation criteria, monetary precision standards, and refund allocation policies.
2. Implement the `process_refund(order: Order, request: RefundRequest) -> RefundResult` method on `RefundService`.
3. Preserve the data models and exceptions defined in `src/atavism_refund/types.py`. Do not modify `types.py`.
4. Ensure all calculations use Python `Decimal` with standard currency precision (two decimal places, e.g. `Decimal("0.01")`).
5. All inputs must be treated as immutable; do not modify incoming `Order`, `Tender`, or `RefundRequest` objects.

