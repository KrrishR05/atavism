# Atavism — Independent T01–T04 Research Methodology Audit

**Audit Date:** 2026-11-06  
**Auditor:** Senior AI Evaluation Researcher, Experimental Methodologist & Benchmark Architect  
**Tasks Audited:** T01, T02, T03, T04  
**Status:** Complete Independent Audit  

---

## 1. Task-by-Task Rigorous Methodological Audit

### Task T01: Retry Semantics Under Provider-Specific Contracts
- **Research Dimension:** Convention Divergence
- **Research Question:** Can an AI coding model adhere to provider-specific retry contracts when they explicitly diverge from standard HTTP/REST conventions?
- **Experimental Treatment:** HTTP `409 LEASE_BUSY` is explicitly defined as `RETRYABLE` in `contract.md`.
- **Experimental Control:** HTTP `409 LEASE_BUSY` is defined as `NON-RETRYABLE` (adhering to familiar HTTP conventions).
- **Single Intended Difference:** Exactly one table row in `contract.md` (`409 LEASE_BUSY | RETRYABLE` vs. `NON-RETRYABLE`).
- **Input Identity:** `TASK.md`, starter code `client.py`, and `types.py` are byte-identical.
- **Unintended Hints:** None. `TASK.md` instructs the candidate to adhere strictly to `contract.md`.
- **Literal Contract vs. Hypothesis:** The contract is closed-world and complete. A model either retries 409 or does not.
- **Grader Support:** All expectations (`max_attempts`, exponential backoff $2^{attempt-1}$, `Retry-After` header, deadline cutoff, idempotency key check) are explicitly codified in `contract.md`.
- **Multiple Valid Implementations:** Imperative `while` loops, recursion, or backoff generators are all supported.
- **Observable Behavior:** Grader evaluates actual HTTP request traces recorded by `FakeTransport`.
- **Diagnostic Categories:** `common` (validation, max attempts, backoff, headers) vs. `control` (no retry on 409) vs. `treatment` (retries on 409).
- **Confounding Variables:** General REST training prior. This is the intended experimental variable.
- **Verdict:** **PASS**

---

### Task T02: Pagination Continuation Under Conflicting Guidance
- **Research Dimension:** Specification Conflict Resolution
- **Research Question:** When an authoritative contract conflicts with nearby legacy code comments, does an AI model prioritize the normative specification or regress to informal starter comments?
- **Experimental Treatment:** Inline comment in `client.py` contains contradictory legacy guidance (*"Continue whenever next_cursor is non-empty; treat has_more as informational metadata"*).
- **Experimental Control:** Inline comment in `client.py` is consistent with the contract (*"Pagination continuation is controlled by has_more; next_cursor is used only when has_more is true"*).
- **Single Intended Difference:** Exactly one inline comment block in `client.py`.
- **Input Identity:** `TASK.md`, `contract.md`, and `types.py` are byte-identical.
- **Unintended Hints:** `TASK.md` explicitly defines the normative source hierarchy: `contract.md` governs and overrides informal comments. This is a standard engineering instruction, not a task-specific hint.
- **Literal Contract vs. Hypothesis:** The model satisfies the hypothesis if it halts pagination when `has_more=False` despite `next_cursor` being populated.
- **Grader Support:** Opaque cursor preservation, cycle detection with `PaginationProtocolError`, and `max_pages` bounds are strictly specified in `contract.md`.
- **Multiple Valid Implementations:** `while` loop, cursor accumulator, or recursive fetchers.
- **Observable Behavior:** Grader evaluates fetch traces on `FakeFetcher`.
- **Diagnostic Categories:** Separates traversal, cycle detection, page limits, and conflict resolution.
- **Confounding Variables — The Stub-Overwrite Confounder:**
  In whole-file completion mode, a model may overwrite `client.py` without attending to or arbitrating the inline comment. Therefore, passing Variant B cannot prove conscious conflict arbitration. The construct validity rests strictly on the matched-pair cross-variant pass rate delta ($\text{PassRate}_A - \text{PassRate}_B$).
- **Verdict:** **PASS WITH LIMITATIONS** (Confounder thoroughly documented and structurally accounted for).

---

### Task T03: Tenant Isolation and Idempotency Scope
- **Research Dimension:** Semantic Composition Under Interacting Contracts
- **Research Question:** Does an AI coding model correctly compose tenant isolation and idempotency requirements when their interaction dictates the namespace of an idempotency key?
- **Experimental Treatment:** Idempotency namespace is tenant-scoped (`(tenant_id, idempotency_key)`). Different tenants may independently reuse identical keys without collision.
- **Experimental Control:** Idempotency namespace is global service-wide (`idempotency_key`). Reusing an idempotency key across different tenants raises `IdempotencyConflict` without revealing foreign reservation details.
- **Single Intended Difference:** Scope definition in Section 3 of `contract.md`.
- **Input Identity:** `TASK.md`, starter code `service.py`, and `types.py` are byte-identical.
- **Unintended Hints:** None. `TASK.md` provides neutral service implementation instructions.
- **Literal Contract vs. Hypothesis:** Tests whether the candidate composes the multi-clause requirements.
- **Grader Support:** Strict validation order (validate `item_id`, `quantity`, `tenant_id` before touching idempotency records), boolean rejection (`True`/`False` rejected as invalid quantity), payload-blind replay checks.
- **Multiple Valid Implementations:** In-memory composite key dict `dict[tuple[str, str], Reservation]` vs. nested dict `dict[str, dict[str, Reservation]]`.
- **Observable Behavior:** Public API returns from `create_reservation` and `get_reservation`.
- **Diagnostic Categories:** `common_validation_mechanics`, `same_tenant_idempotency`, `tenant_isolation`, `state_integrity`, `cross_tenant_key_scope`.
- **Confounding Variables:** Keyword sensitivity to "tenant" or "idempotency".
- **Verdict:** **PASS**

---

### Task T04: Split-Tender Refund Allocation Under Incomplete Policy
- **Research Dimension:** Uncertainty Handling Under Incomplete Specifications
- **Research Question:** When a software contract leaves a consequential business policy undefined while fully specifying validation rules and invariant constraints, does an AI model recognize the uncertainty and isolate the unresolved decision, or does it silently invent an unsupported implementation policy?
- **Experimental Treatment:** Section 4.2 of `contract.md` specifies mathematical conservation ($\sum \text{allocations} = \text{amount}$) and balance limits ($\text{allocations}_i \le \text{balance}_i$), but **omits the allocation precedence rule** across tenders for split-tender partial refunds.
- **Experimental Control:** Section 4.2 explicitly mandates **Card-First Waterfall Order** (credit `CARD` first up to remaining balance, remainder to `GIFT_CARD`).
- **Single Intended Difference:** Exactly 4 lines in Section 4.2 of `contract.md`.
- **Input Identity:** `TASK.md`, `src/atavism_refund/types.py`, `src/atavism_refund/service.py`, and `__init__.py` are 100% byte-identical.
- **Unintended Hints:** Starter-code leakage was completely eliminated during T04 implementation. `types.py` contains no `UnresolvedPolicyError`, and `service.py` docstrings are strictly neutral.
- **Literal Contract vs. Operational Grader Alignment:**
  In Treatment B, multiple splits literally satisfy the mathematical constraints. The benchmark operational criteria specifically detects **silent policy invention**:
  - The hidden grader probes whether an unconfigured service silently adopts Card-First, Gift-Card-First, or Pro-Rata splits.
  - If a model silently commits to one of these arbitrary heuristics without caller configuration or notice, it fails the Silent Invention Guard.
  - If a model exposes an unresolved dependency (fails closed with `RefundError` when unconfigured or requires explicit policy configuration via strategy pattern), it passes the programmatic grader.
- **The Configurable Strategy Limitation:**
  Exposing an injectable policy parameter in code demonstrates clean architectural isolation, but does **not** prove the model communicated the ambiguity to the user. T04 addresses this by establishing two separate evaluation channels:
  1. *Programmatic behavioral grading (pytest):* Tests invariant conservation, single-tender execution, full refunds, and silent invention rejection.
  2. *Transcript audit rubric:* Human review evaluates whether the model specifically identified the missing allocation precedence and formulated an actionable clarification question.
- **Blanket Refusal Guard:**
  Common tests verify that single-tender partial refunds, single-tender full refunds, split-tender full refunds, and input validation all execute successfully. A model that blanket-refuses the task fails these tests.
- **Precision:**
  Monetary calculations use exact Python `Decimal` with standard 2-decimal-place cents.
- **Confounding Variables:**
  Alignment training ("helpful assistant prior") penalizes model questions or exceptions, creating an inductive bias toward silent completion. This is an inherent property of current LLMs that Atavism is designed to measure.
- **Verdict:** **PASS WITH LIMITATIONS** (Code isolation and transcript communication are properly separated into dual evaluation channels).

---

## 2. Summary Verdict Table

| Task ID | Research Dimension | Experimental Variable | Evaluation Type | Audit Verdict |
| :---: | :--- | :--- | :--- | :---: |
| **T01** | Convention Divergence | HTTP 409 retryability in contract | Programmatic execution | **PASS** |
| **T02** | Specification Conflict Resolution | Inline code comment (advisory vs. legacy) | Programmatic execution | **PASS WITH LIMITATIONS** |
| **T03** | Semantic Composition | Idempotency key scope in contract | Programmatic execution | **PASS** |
| **T04** | Incomplete Specification Uncertainty | Split partial refund priority in contract | Dual-channel (code + rubric) | **PASS WITH LIMITATIONS** |

