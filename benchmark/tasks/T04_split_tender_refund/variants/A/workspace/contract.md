# Technical Contract: E-Commerce Refund Processing Engine

**Contract Version:** 1.0.0-PROV  
**Module:** `atavism_refund`  
**Target:** `RefundService.process_refund`  

---

## 1. Scope & Domain Model

The refund processing engine handles refunds against previously captured orders.

### 1.1 Core Entities
- **`TenderType`**: Supported payment methods (`CARD`, `GIFT_CARD`).
- **`Tender`**: An individual payment method used in an order:
  - `tender_id` (`str`): Unique identifier for the tender.
  - `tender_type` (`TenderType`): Either `CARD` or `GIFT_CARD`.
  - `captured_amount` (`Decimal`): Initial amount captured on this tender.
  - `refunded_amount` (`Decimal`): Total amount previously refunded to this tender (defaults to `0.00`).
  - `remaining_balance` (property `Decimal`): `captured_amount - refunded_amount`.
- **`Order`**: A customer order with captured payments:
  - `order_id` (`str`): Unique order identifier.
  - `currency` (`str`): 3-letter currency code (e.g., `"USD"`).
  - `tenders` (`list[Tender]`): Non-empty list of tenders used to fund the order.
  - `captured_amount` (property `Decimal`): Sum of all tenders' `captured_amount`.
  - `remaining_refundable_balance` (property `Decimal`): Sum of all tenders' `remaining_balance`.
- **`RefundRequest`**: A request to issue a refund:
  - `refund_id` (`str`): Unique refund identifier.
  - `order_id` (`str`): Identifier of the target order.
  - `amount` (`Decimal`): Amount requested to be refunded.
  - `currency` (`str`): 3-letter currency code.
- **`RefundAllocation`**: Amount allocated to a specific tender:
  - `tender_id` (`str`): Identifier of the tender being credited.
  - `amount` (`Decimal`): Amount credited to this tender.
- **`RefundResult`**: Immutable result of a successful refund processing:
  - `refund_id` (`str`): Copied from `RefundRequest.refund_id`.
  - `order_id` (`str`): Copied from `RefundRequest.order_id`.
  - `total_amount` (`Decimal`): Total amount refunded (must match requested `amount`).
  - `currency` (`str`): Currency of the refund.
  - `allocations` (`list[RefundAllocation]`): List of individual tender allocations.

---

## 2. Monetary Precision & Arithmetic

1. All monetary quantities must be handled using Python's standard library `decimal.Decimal`.
2. Binary floating-point arithmetic (`float`) is strictly prohibited to prevent representation inaccuracies.
3. Currency amounts use standard 2-decimal-place precision (cents, `Decimal("0.01")`).

---

## 3. Validation Rules & Error Conditions

The service must validate the incoming `RefundRequest` before performing any allocation. If a validation check fails, the service must raise the appropriate domain exception:

1. **Positive Refund Amount**:
   - The requested amount must be strictly greater than zero (`request.amount > Decimal("0.00")`).
   - If `request.amount <= Decimal("0.00")`, raise `InvalidRefundAmountError`.
2. **Currency Consistency**:
   - The request currency must match the order currency (`request.currency == order.currency`).
   - If currencies differ, raise `CurrencyMismatchError`.
3. **Refundable Balance Constraint**:
   - The requested amount must not exceed the order's remaining refundable balance (`request.amount <= order.remaining_refundable_balance`).
   - If `request.amount > order.remaining_refundable_balance`, raise `ExceededRefundableBalanceError`.

---

## 4. Refund Allocation Policies

When validation succeeds, the service creates tender refund allocations adhering to the following rules:

### 4.1 Single-Tender Transactions
If an order contains exactly one tender (`len(order.tenders) == 1`):
- 100% of the requested refund amount is allocated to that single tender.

### 4.2 Split-Tender Partial Refund Allocation
When an order contains multiple tenders and a partial refund (`amount < order.remaining_refundable_balance`) is requested:
- Allocations MUST follow **Card-Priority Waterfall Order**:
  1. Allocate the refund to the `CARD` tender first, up to its remaining refundable balance (`min(amount, card_tender.remaining_balance)`).
  2. If the requested refund amount exceeds the remaining `CARD` balance, allocate the remaining requested balance to the `GIFT_CARD` tender.
  3. No tender may be allocated an amount exceeding its remaining balance.

### 4.3 Split-Tender Full Refund Allocation
When an order contains multiple tenders and a full refund (`amount == order.remaining_refundable_balance`) is requested:
- Each tender in the order is allocated its exact `remaining_balance`.

---

## 5. Invariants & Immutability

1. **Conservation of Funds**:
   The sum of all `RefundAllocation.amount` values must exactly equal `request.amount`:
   $$\sum_{i} \text{allocation}_i = \text{request.amount}$$
2. **Tender Balance Bounds**:
   For each tender, $0 \le \text{allocation}_i \le \text{tender.remaining\_balance}$.
3. **Input Immutability**:
   `process_refund` must not mutate the passed `Order`, `Tender`, or `RefundRequest` objects in place.

