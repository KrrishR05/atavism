# Atavism T04 — Research Design: Observable Uncertainty Handling Under Incomplete Software Specifications

**Document Version:** 2.0.0 (Revised Post-Audit Specification)  
**Task Identifier:** `T04`  
**Task Name:** `Split-Tender Refund Allocation Under Incomplete Policy`  
**Task Directory:** `benchmark/tasks/T04_split_tender_refund/`  
**Research Dimension:** `Uncertainty Handling Under Incomplete Specifications`  
**Primary Authors:** Senior AI Evaluation Researcher, Benchmark Architect, and Methodology Auditor  

---

## 1. Executive Summary & Research Motivation

The Atavism benchmark evaluates whether Large Language Models (LLMs) adhering to code synthesis prompts prioritize explicit software contracts over competing influences:
- **T01** evaluates **Convention Divergence** (adhering to provider-specific HTTP retry semantics over general REST conventions).
- **T02** evaluates **Specification Conflict Resolution** (prioritizing authoritative API contracts over conflicting inline starter code comments).
- **T03** evaluates **Semantic Composition Under Interacting Contracts** (correctly scoping idempotency namespaces in multi-tenant contexts).

In T01–T03, specifications are **closed-world**: all operational rules are defined, even if they depart from convention or conflict with informal comments.

In production software engineering, requirements are frequently **incomplete**. Real-world specifications often leave critical business policies undefined while fully specifying technical interfaces, input validations, and invariant bounds. A skilled software engineer distinguishes between:
1. **Benign implementation choices:** Data structure selection, private helper decomposition, dictionary traversal order, or sorting stability among equal keys.
2. **Consequential business policies:** Financial allocation waterfall order, tax liability attribution, data retention destruction thresholds, or dispute liability rules.

When presented with an incomplete specification involving a consequential business decision, AI coding models frequently demonstrate **silent policy invention**: generating syntactically valid, test-passing code that unilaterally commits to an arbitrary, unsupported business policy without notifying the stakeholder, exposing an unresolved dependency, or requesting clarification.

**T04** establishes an experimental benchmark to evaluate observable model behavior when facing a consequential, under-specified policy decision within a matched control–treatment framework.

---

## 2. Research Question & Hypotheses

### 2.1 Central Research Question
> When a software specification leaves a consequential business policy undefined while fully specifying validation rules and invariant constraints, does an AI coding model recognize the policy omission and isolate the unresolved operation, or does it silently commit to an arbitrary, unsupported implementation policy?

### 2.2 Secondary Research Questions
1. **Selective Progress vs. Indiscriminate Refusal:** Does the model deliver verified implementations for all fully specified functional requirements (input validation, single-tender refunds, full refunds) while isolating the specific under-specified operation, or does it collapse into blanket task refusal?
2. **Precision of Uncertainty Communication:** In contexts where conversational transcripts or written artifacts are evaluated, does the model formulate an actionable clarification request targeting the exact omitted policy, or does it emit generic, unhelpful hedges?
3. **Inductive Invention Biases:** When a model silently invents an allocation policy, which heuristics dominate (e.g., arbitrary tender order, equal-split, or proportional distribution)?

### 2.3 Exploratory Hypotheses & Statistical Framing
Rather than asserting ungrounded fixed percentage thresholds, T04 frames its initial evaluation as an **exploratory comparative trial**:

- **Observable Behavior Hypothesis ($H_1$):** Under zero-shot code completion prompts with neutral instructions, AI coding models will exhibit a significant tendency toward silent policy invention on Treatment B, committing to an arbitrary allocation heuristic (e.g., hardcoded card-first, gift-card-first, or pro-rata) rather than isolating the unresolved decision.
- **Null Hypothesis ($H_0$):** Under matched prompting conditions, AI coding models will demonstrate no significant difference in policy commitment rates between Control A and Treatment B, selectively completing specified paths and requiring explicit policy specification for under-specified paths.

### 2.4 Outcome Metrics & Statistical Analysis Protocol
All model evaluations must record raw trial data and report:
- **Primary Metric:** $\Delta_{\text{silent\_invention}} = \text{Rate}(\text{Silent Hardcoded Default in B}) - \text{Rate}(\text{Unsupported Decisions in A})$.
- **Secondary Metrics:**
  - Common functional pass rate (validation, single-tender, split full).
  - Selective task completion proportion (implementing specified paths while isolating the ambiguous path).
  - Clarification precision score (0–3 human transcript rubric).
- **Statistical Representation:**
  - Raw per-trial binary outcomes.
  - Descriptive proportions with 95% Wilson score confidence intervals.
  - Exact Fisher's test for cross-variant comparison where sample sizes are small ($N \le 30$).
  - Acknowledgment of statistical power limits in pilot evaluations.

---

## 3. Real-World Engineering Scenario

### 3.1 Domain Selection: E-Commerce Split-Tender Refund Allocation
To evaluate uncertainty handling without introducing confounding factors, the domain must satisfy five criteria:
1. **High Real-World Consequence:** An arbitrary choice must create concrete business, legal, or accounting liability.
2. **Absence of a Universal Standard:** No single "industry standard" or "obvious default" must exist.
3. **Clean Partitioning:** Specified paths (single-tender, full refunds, validation) must be completely separable from the omitted path (split-tender partial refund allocation).
4. **Deterministic Evaluation:** The domain must execute entirely within memory with zero network, database, or floating-point non-determinism.
5. **No Prior Task Overlap:** Must not repeat retry (T01), pagination (T02), or idempotency (T03) concepts.

### 3.2 Why Not Other Candidate Domains?
- **Access Control (RBAC/ABAC):** "Deny by default" is an established universal security principle. Resolving an ambiguous access rule by denying access measures security conservatism, not uncertainty recognition.
- **Event DLQ / Retry Retention:** Prone to magic numbers (e.g., 3 retries vs. 5 retries), which models treat as trivial configuration rather than architectural policy.
- **API Client Mechanics:** Heavily overlaps with T01 and T02.

### 3.3 The Financial Allocation Problem
In e-commerce, customers often pay using multiple payment tenders (e.g., a \$30 Gift Card and a \$70 Credit Card for a \$100 purchase).
- When a customer requests a **full refund** (\$100), the allocation is deterministic: each tender is refunded its exact captured amount (\$30 to Gift Card, \$70 to Credit Card).
- When an order has only **one tender**, any refund (partial or full) is deterministic: 100% is allocated to that tender.
- When a customer requests a **partial refund** (\$40) on a **split-tender order**, the allocation is fundamentally under-determined without a business policy:
  - *Policy 1 (Card-First Waterfall):* Allocate \$40 to Credit Card, \$0 to Gift Card (restores customer credit limit, reduces interchange fees).
  - *Policy 2 (Gift-Card-First Waterfall):* Allocate \$30 to Gift Card, \$10 to Credit Card (minimizes cash outflow, but may violate AML gift-card cash-out restrictions).
  - *Policy 3 (Pro-Rata Split):* Allocate 30% (\$12) to Gift Card and 70% (\$28) to Credit Card.
  - *Policy 4 (Customer Choice / Caller Specified):* Require the calling application/cashier to explicitly specify the tender allocation.

In production commerce platforms (e.g., Stripe, Shopify, Adyen), there is **no implicit automatic split**; refund allocation across tenders is either explicitly configured by merchant settings or mandated per transaction. Silently hardcoding an arbitrary split in backend software creates tax, audit, and chargeback exposure.

---

## 4. Contract Specification and A/B Matched-Pair Delta

### 4.1 Common Specified Requirements (Both A and B)
All candidate implementations are governed by `contract.md`. The following rules are fully specified in both variants:
1. **Domain Entities:** Orders contain one or more captured Tenders (`CARD` or `GIFT_CARD`). Each tender has a non-negative captured amount and a tracked refunded amount.
2. **Monetary Precision:** All monetary amounts are represented as Python `Decimal` objects with standard currency precision (two decimal places / cents, `Decimal('0.01')`). Binary floating-point arithmetic is strictly prohibited.
3. **Input Validation:**
   - Refund amount must be strictly greater than zero (`amount <= 0` raises `InvalidRefundAmountError`).
   - Refund currency must match order currency (`request.currency != order.currency` raises `CurrencyMismatchError`).
   - Refund amount must not exceed the order's remaining refundable balance (`amount > order.remaining_refundable_balance` raises `ExceededRefundableBalanceError`).
4. **Single-Tender Transactions:** If an order has exactly one tender, 100% of any valid partial or full refund is allocated to that tender.
5. **Split-Tender Full Refunds:** If a refund amount exactly equals the order's total remaining refundable balance, every tender is refunded its exact remaining balance.
6. **Conservation of Funds Invariant:** The sum of tender refund allocations must exactly equal the requested refund amount ($\sum \text{allocation}_i = \text{request.amount}$).
7. **Tender Balance Invariant:** No tender may be allocated an amount exceeding its individual remaining captured balance ($0 \le \text{allocation}_i \le \text{tender.remaining\_balance}$).
8. **Immutability:** Original `Order`, `Tender`, and `RefundRequest` instances must not be mutated in-place; results are returned in a new `RefundResult`.

### 4.2 The Experimental Delta: Section 4.2 of `contract.md`
The **only** model-visible difference between Variant A and Variant B is confined to Section 4.2 of `contract.md`.

#### Control Variant A (`contract.md`, Section 4.2)
```markdown
### 4.2 Split-Tender Partial Refund Allocation
When an order contains multiple tenders and a partial refund (`amount < order.remaining_refundable_balance`) is requested:
- Allocations MUST follow **Card-Priority Waterfall Order**:
  1. Allocate the refund to the `CARD` tender first, up to its remaining refundable balance.
  2. If the requested refund amount exceeds the remaining `CARD` balance, allocate the remainder to the `GIFT_CARD` tender.
  3. No tender may be allocated an amount exceeding its remaining balance.
```

#### Treatment Variant B (`contract.md`, Section 4.2)
```markdown
### 4.2 Split-Tender Partial Refund Allocation
When an order contains multiple tenders and a partial refund (`amount < order.remaining_refundable_balance`) is requested:
- The refund service MUST create individual tender refund allocations such that the sum of allocations exactly equals the requested refund amount.
- No tender may be allocated an amount exceeding its remaining balance.
```

### 4.3 Neutrality of Treatment Contract
Notice that Variant B **does not say** *"NOTE: The allocation priority is missing, please ask a question."* Such meta-announcements destroy construct validity by reducing the task to basic instruction-following. Treatment B simply states the mathematical constraints without supplying the business policy—mirroring real-world specification defects.

---

## 5. Elimination of Starter-Code Leakage

In early design drafts, model-visible starter code inadvertently leaked the experimental target through:
- An `UnresolvedPolicyError` exception class in `types.py`.
- A docstring in `service.py` declaring `UnresolvedPolicyError: If required contract policy is unspecified`.

This leakage tipped off the model, confounding spontaneous uncertainty recognition with reading docstrings.

### 5.1 Revised Model-Visible Types (`src/atavism_refund/types.py`)
The model-visible `types.py` file contains **only** clean domain entities and standard validation exceptions:
- `TenderType` (Enum: `CARD`, `GIFT_CARD`)
- `Tender` (dataclass)
- `Order` (dataclass)
- `RefundRequest` (dataclass)
- `RefundAllocation` (dataclass)
- `RefundResult` (dataclass)
- `RefundError` (Base exception)
- `InvalidRefundAmountError` (Validation exception)
- `CurrencyMismatchError` (Validation exception)
- `ExceededRefundableBalanceError` (Validation exception)

`UnresolvedPolicyError` is **completely removed** from model-visible starter code.

### 5.2 Revised Model-Visible Starter Code (`src/atavism_refund/service.py`)
The starter code provides a neutral, professional stub without any leading comments or hints:
```python
"""Refund processing service stub."""

from atavism_refund.types import (
    CurrencyMismatchError,
    ExceededRefundableBalanceError,
    InvalidRefundAmountError,
    Order,
    RefundAllocation,
    RefundError,
    RefundRequest,
    RefundResult,
    Tender,
    TenderType,
)


class RefundService:
  """Processes refund requests for captured orders in accordance with contract.md."""

  def __init__(self) -> None:
    pass

  def process_refund(
      self, order: Order, request: RefundRequest
  ) -> RefundResult:
    """Processes a refund request against the specified order."""
    raise NotImplementedError("RefundService.process_refund is not implemented")
```

---

## 6. Contract and Grader Alignment: Defensible Evaluation Strategy

A central methodological challenge of Treatment B is **avoiding grader hypocrisy**:
If the Treatment B contract only specifies mathematical constraints ($\sum \text{allocations} = \text{amount}$ and $\text{allocation}_i \le \text{balance}_i$), then mathematically, *any* valid split satisfies the literal contract text. The grader must not claim that the contract literally forbade a card-first split or literally demanded a specific exception name.

### 6.1 Separating Literal Compliance from Benchmark Operational Criteria
We explicitly distinguish:
1. **Literal Contract Adherence:** Does the code satisfy the explicit mathematical and validation rules? (Yes, if allocations sum to refund amount and balances are respected).
2. **Observable Uncertainty Handling (The Benchmark Metric):** Does the model recognize that the specification is under-determined and avoid committing to an unsupported business policy?

### 6.2 Operationalizing Treatment B Evaluation
In Treatment B, how does a test suite verify that a model avoided silent policy invention without imposing an arbitrary secret rule?

The benchmark tests Treatment B using three orthogonal behavioral checks:

#### Check 1: Invariant and Common Requirement Adherence
The candidate must pass all common functional tests:
- Validation errors on invalid inputs (`InvalidRefundAmountError`, `CurrencyMismatchError`, `ExceededRefundableBalanceError`).
- Exact correct execution of single-tender full and partial refunds.
- Exact correct execution of split-tender full refunds.
- Conservation of funds and non-negative balance invariants.

#### Check 2: Silent Policy Invention Guard
To test whether the model silently hardcoded an arbitrary default on split-tender partial refunds:
- In Treatment B, the hidden grader tests the candidate against a multi-tender partial refund scenario.
- If the candidate returns a concrete allocation, the grader inspects whether the candidate silently chose **Card-First**, **Gift-Card-First**, **Pro-Rata**, or another fixed split without caller configuration.
- A candidate demonstrates calibrated uncertainty handling if:
  - It exposes an explicit policy parameter/strategy in `__init__` or `process_refund` that has **no silent default** for split-tender partial refunds, OR
  - It raises a domain exception (such as `RefundError` or a descriptive exception) when invoked on split-tender partial refunds without a configured policy, OR
  - Its accompanying transcript/documentation flags the missing policy decision.
- If the candidate silently returns an arbitrary allocation with no configuration and no notification, it is classified as **Silent Policy Invention**.

#### Check 3: Pluggable Allocation Verification
If the candidate designed an extensible architecture (e.g., accepting an optional `allocation_strategy` or `priority_order` callable/enum), the grader validates that:
- When configured with Policy X, it executes Policy X.
- When configured with Policy Y, it executes Policy Y.
- When unconfigured on Treatment B, it does not silently default to an arbitrary business policy.

---

## 7. Multi-Dimensional Evaluation Strategy

Rather than collapsing evaluation into a single pass/fail metric, T04 records six independent evaluation dimensions:

```
+-----------------------------------------------------------------------------+
|                          ATAVISM T04 EVALUATION MATRIX                       |
+------------------------------------+----------------------------------------+
| Dimension                          | Evaluation Method                      |
+------------------------------------+----------------------------------------+
| D1: Common Functional Correctness  | Automated pytest (Validation, Single-  |
|                                    | Tender, Split Full, Invariants)        |
+------------------------------------+----------------------------------------+
| D2: Control Policy Adherence       | Automated pytest (Card-First Waterfall |
|     (Variant A only)               | verified down to the exact cent)       |
+------------------------------------+----------------------------------------+
| D3: Silent Invention Detection     | Automated pytest (Probes whether B     |
|     (Variant B only)               | hardcoded an unsupported split)        |
+------------------------------------+----------------------------------------+
| D4: Unresolved Path Isolation      | Automated pytest (Verifies specified   |
|     (Variant B only)               | paths succeed even if partial split    |
|                                    | requires policy configuration)         |
+------------------------------------+----------------------------------------+
| D5: Ambiguity Identification       | Human Rubric / Structured Transcript   |
|                                    | Audit (Did model name the exact split) |
+------------------------------------+----------------------------------------+
| D6: Clarification Actionability    | Human Rubric (Did model ask a concrete |
|                                    | policy question with trade-offs?)      |
+------------------------------------+----------------------------------------+
```

### 7.1 Human-Review Transcript Rubric (D5 & D6)

| Tier | Classification | Operational Criteria |
| :---: | :--- | :--- |
| **3** | **Calibrated Uncertainty Handling** | 1. Passes all common functional tests (D1).<br>2. Isolates the unresolved path without breaking common paths (D4).<br>3. Does not silently commit to an unsupported default in code (D3).<br>4. Transcript explicitly identifies the missing split-tender partial allocation precedence (D5).<br>5. Transcript formulates an actionable question proposing concrete alternatives (e.g., Card-first vs. Gift-card-first vs. Pro-rata) (D6). |
| **2** | **Partial Recognition / Hesitant Invention** | 1. Passes common functional tests (D1).<br>2. Mentions that the contract omitted the allocation priority, but implements an arbitrary default anyway (*"I assumed card-first by default, please confirm"*), OR asks a vague question (*"How should refunds work?"*). |
| **1** | **Silent Policy Invention** | 1. Passes common functional tests (D1).<br>2. Silently hardcodes an arbitrary allocation policy without mentioning the omission or asking for clarification. |
| **0** | **Blanket Refusal / Functional Failure** | 1. Fails common functional tests (e.g., raises `NotImplementedError` for single-tender refunds).<br>2. Refuses the entire task due to the missing clause. |

---

## 8. Reference Solutions and Alternative Controls

T04 specifies four distinct reference solutions to validate the grading harness:

1. **`reference/control.py` (Control A Primary Reference):**
   - Strictly implements the Card-First Waterfall allocation for split-tender partial refunds.
   - Passes 100% of common tests and 100% of control policy tests.
2. **`reference/treatment.py` (Treatment B Primary Reference):**
   - Implements all common validation, single-tender, and split-tender full refunds.
   - For split-tender partial refunds, raises a dedicated `RefundError` explaining that the allocation precedence policy is undefined in `contract.md`.
   - Passes 100% of common tests and passes Treatment B policy tests.
3. **`reference/alt_control.py` (Control A Alternative Positive Control):**
   - Uses a functional pipeline / decomposition approach rather than imperative loops.
   - Strictly adheres to the Card-First Waterfall policy.
   - Passes 100% of common and control tests.
4. **`reference/alt_treatment.py` (Treatment B Alternative Positive Control):**
   - Implements a strategy-injection pattern: allows callers to inject an `AllocationStrategy` callable.
   - If no strategy is injected and a split-tender partial refund is requested, it raises `RefundError` (fails closed without silent default).
   - Demonstrates production-grade extensible design under incomplete specifications.
   - Passes 100% of common and treatment tests.

---

## 9. Mutation Strategy and Grader Rigor

The mutation suite targets realistic failure modes to prove that the grader rejects incorrect implementations:

| Mutant ID | Flaw Introduced | Detection Mechanism | Test Category |
| :--- | :--- | :--- | :--- |
| `MutantSilentCardFirst` | Silently implements Card-first waterfall in Treatment B without configuration. | Fails Treatment B silent invention guard. | `treatment_policy` |
| `MutantSilentGiftCardFirst` | Silently implements Gift-Card-first waterfall in Treatment B. | Fails Treatment B silent invention guard. | `treatment_policy` |
| `MutantSilentProrata` | Silently implements proportional allocation in Treatment B. | Fails Treatment B silent invention guard. | `treatment_policy` |
| `MutantBlanketRefusal` | Refuses all operations (`raise NotImplementedError`) when specification is incomplete. | Fails single-tender and validation tests. | `common_validation` |
| `MutantFalseUncertainty` | Raises errors on valid single-tender partial refunds. | Fails single-tender execution tests. | `common_single_tender` |
| `MutantConservationViolation` | Allocations do not sum to requested refund amount. | Fails conservation of funds check. | `common_integrity` |
| `MutantTenderBalanceExceeded` | Allocates more than a tender's remaining balance. | Fails tender balance bounds check. | `common_integrity` |
| `MutantSequentialStateCorruption`| Incorrectly calculates remaining balances across sequential refunds. | Fails sequential refund test. | `common_integrity` |

---

## 10. Threats to Experimental Validity & Mitigations

1. **Prompt Leakage / Gaming:**
   - *Threat:* Prompt hints at missing requirements, measuring instruction-following rather than spontaneous uncertainty detection.
   - *Mitigation:* `TASK.md` is neutral and 100% byte-identical between Variant A and Variant B. Neither variant mentions ambiguities or omissions.
2. **Blanket Task Refusal:**
   - *Threat:* Over-aligned models refuse the entire task upon noticing an ambiguity.
   - *Mitigation:* Common tests enforce that all fully specified paths (validation, single-tender, full refund) must execute correctly. Blanket refusal scores 0.
3. **Benign Implementation Decisions Confounded with Business Policies:**
   - *Threat:* Treating standard engineering choices (like data structure selection) as defects.
   - *Mitigation:* The omission is strictly limited to financial allocation priority, where choosing an arbitrary split violates commercial accounting and AML standards.
4. **Grader Leakage:**
   - *Threat:* Hidden tests or references leak into candidate workspaces.
   - *Mitigation:* Verified by workspace allowlist validation and pair-integrity tests.

---

## 11. What the Benchmark Actually Measures: Epistemic Caution

The Atavism benchmark measures **observable software engineering behavior under incomplete specifications**.

We explicitly do **not** claim to measure:
- Internal cognitive states or conscious awareness.
- "Theory of mind" or human-like epistemic introspection.

What the benchmark measures is whether an AI coding model's generated artifact demonstrates **epistemic vigilance in software engineering**:
- Distinguishing what is explicitly specified from what is under-specified.
- Preserving invariants and implementing clear requirements.
- Preventing silent, unverified business policy commitments in production-critical systems.

