# Atavism

**Contract Intelligence and Specification Adherence in LLM-Based Software Engineering**

Atavism is a research-driven benchmark developed for the **micro1 Eval Hackathon** hosted on HackerRank. It evaluates whether AI coding models reliably interpret and implement explicit software specifications when those specifications conflict with familiar programming conventions or contain interacting technical requirements.

---

## 1. Research Overview

### Central Research Question
> *Can AI coding models reliably interpret and implement explicit software contracts when those contracts differ from familiar programming conventions or conflict with informal implementation guidance?*

### Motivation
In production software engineering, following a familiar implementation pattern or common heuristic is often insufficient—and sometimes dangerously incorrect. A specific cloud provider or internal service may deliberately alter retry semantics (such as retrying conflict states under optimistic concurrency), event-stream termination rules, or pagination continuation authority.

Current AI coding models frequently generate plausible, functional-looking code that quietly violates explicit technical requirements, falling back instead on patterns learned from pretraining corpora or nearby informal comments. Atavism was created to measure this failure mode rigorously and reproducibly.

### Paired Benchmark Methodology
To isolate contract adherence from baseline coding proficiency, Atavism utilizes **controlled, paired evaluation tasks**:

- **Control Variant (A):** The task specifies conventional software behavior or consistent inline guidance.
- **Treatment Variant (B):** The task introduces a controlled departure—such as an explicit deviation from convention in the contract (T01) or a conflicting legacy implementation comment in the starter code (T02).
- **Control Invariance:** Both variants share identical environments, type signatures, input data, dependencies, and evaluation standards.
- **Measurable Gap:** Differences in model pass rates between Variant A and Variant B isolate the model's tendency to succumb to prior bias versus following explicit documentation.

---

## 2. Research Dimensions

Atavism establishes five foundational research dimensions for contract evaluation:

| Dimension | Description | Benchmark Task |
|---|---|---|
| **Convention Divergence** | Adhering to explicit behavior that deliberately departs from common conventions. | **T01** (Retry Semantics) |
| **Specification Conflict Resolution** | Prioritizing authoritative API contracts over conflicting legacy implementation guidance. | **T02** (Pagination Authority) |
| **Semantic Composition** | Preserving multiple interacting technical requirements simultaneously (e.g., tenant isolation and idempotency scope). | **T03** (Tenant Idempotency) |
| **Uncertainty Handling** | Recognizing missing, ambiguous, or contradictory specifications rather than guessing. | Staged |
| **Contract Consistency** | Maintaining specified behavior across entire implementations without drift. | Staged |

---

## 3. Implemented Benchmark Tasks

### T01: Retry Semantics Under Provider-Specific Contracts
- **Research Dimension:** Convention Divergence
- **Scenario:** Implement a deterministic retry client (`send_with_retry`) for Meridian Gateway with exponential backoff, deadline enforcement, `Retry-After` precedence, and idempotency key safety.
- **Core Experimental Variable:**
  - *Variant A (Control):* HTTP `409 LEASE_BUSY` is **NOT retryable** (conventional HTTP heuristic).
  - *Variant B (Treatment):* HTTP `409 LEASE_BUSY` is **RETRYABLE** (explicit provider contract).

### T02: Pagination Continuation Under Conflicting Implementation Guidance
- **Research Dimension:** Specification Conflict Resolution
- **Scenario:** Implement a deterministic cursor pagination aggregator (`collect_all_items`) for Meridian Gateway across multiple pages.
- **Core Semantics:**
  - `has_more` is the **sole authority** deciding whether pagination continues.
  - A populated `next_cursor` on a terminal page (`has_more=False`) is an informational checkpoint and must **never** trigger another page fetch.
  - When `has_more=True`, a non-empty, non-whitespace cursor is mandatory, and pagination cycles must be detected and rejected with `PaginationProtocolError`.
  - `max_pages` must be enforced, rejecting non-int/boolean values.
- **Core Experimental Variable:**
  - *Variant A (Control):* Inline comment agrees with contract:
    ```python
    # Pagination continuation is controlled by has_more.
    # next_cursor is used only when has_more is true.
    ```
  - *Variant B (Treatment):* Inline comment contains conflicting legacy guidance:
    ```python
    # Legacy pagination behavior:
    # Continue whenever next_cursor is non-empty.
    # Treat has_more as informational metadata.
    ```
  - `TASK.md` explicitly establishes the source hierarchy: `contract.md` is normative and overrides inline comments. Both variants share identical `contract.md` and `TASK.md`.

### T03: Tenant Isolation and Idempotency Scope
- **Research Dimension:** Semantic Composition Under Interacting Contracts
- **Scenario:** Implement a deterministic multi-tenant reservation coordinator (`ReservationService`) with injected identifier allocation (`id_factory`).
- **Core Semantics:**
  - `tenant_id`, `item_id`, and `idempotency_key` must be non-empty, non-whitespace strings.
  - `quantity` must be a positive integer; Python `bool` values (`True`/`False`) must be rejected despite subclassing `int`.
  - Validation must occur before checking idempotency records; invalid requests must not mutate state or consume identifiers.
  - Replays with identical payload return the original `Reservation` without allocating new IDs.
  - Replays with different payloads raise `IdempotencyConflict` without mutating stored state.
  - `get_reservation` retrieves only reservations belonging to the requesting tenant; foreign or non-existent reservations return `None`.
- **Core Experimental Variable:**
  - *Variant A (Control):* Idempotency namespace is **global across the service** (`idempotency_key`). Reusing an idempotency key across different tenants raises `IdempotencyConflict` without disclosing foreign details.
  - *Variant B (Treatment):* Idempotency namespace is **scoped per tenant** (`(tenant_id, idempotency_key)`). Different tenants may independently reuse identical keys without conflict.

### T04: Split-Tender Refund Allocation Under Incomplete Policy
- **Research Dimension:** Uncertainty Handling Under Incomplete Specifications
- **Scenario:** Implement an e-commerce refund processor (`RefundService.process_refund`) using exact Python `Decimal` arithmetic.
- **Core Semantics:**
  - `amount` must be strictly positive (`InvalidRefundAmountError`).
  - `currency` must match order currency (`CurrencyMismatchError`).
  - `amount` must not exceed order's remaining refundable balance (`ExceededRefundableBalanceError`).
  - Single-tender transactions allocate 100% of partial or full refunds to that tender.
  - Split-tender full refunds allocate each tender's exact remaining balance.
  - Sum of allocations must strictly conserve funds ($\sum \text{allocation}_i = \text{amount}$).
  - Original inputs are immutable; no in-place mutation of orders or tenders.
- **Core Experimental Variable:**
  - *Variant A (Control):* Split-tender partial refunds explicitly follow **Card-Priority Waterfall Order** (allocating to `CARD` first up to remaining balance, remainder to `GIFT_CARD`).
  - *Variant B (Treatment):* Contract specifies mathematical conservation constraints but **omits the allocation precedence rule**. The benchmark tests whether the model silently invents an arbitrary policy (Card-first, Gift-card-first, Pro-Rata) or isolates the unresolved decision (failing closed or requiring explicit policy configuration).

---

## 4. Repository Architecture

Atavism strictly isolates private evaluation fixtures from model-visible workspaces:

```text
atavism/
├── README.md                           # Benchmark documentation and reproducibility guide
├── pyproject.toml                      # Build and test configuration
├── .gitignore                          # VCS exclusions
├── .env.example                        # Trial environment template
│
├── docs/
│   ├── research_charter.md             # Theoretical foundation and research scope
│   ├── research_protocol.md            # Experimental protocol and metrics definition
│   └── task_design.md                  # Task authoring and pair-control principles
│
├── benchmark/
│   └── tasks/
│       ├── T01_retry_semantics/
│       │   ├── task.json               # Task metadata and allowlist definition
│       │   ├── variants/
│       │   │   ├── A/workspace/        # Model-visible workspace (Control)
│       │   │   └── B/workspace/        # Model-visible workspace (Treatment)
│       │   └── private/                # Hidden evaluation files
│       │       ├── reference/          # Reference implementations (control.py, treatment.py)
│       │       ├── tests/              # Hidden test suites (conftest, common, control, treatment)
│       │       └── mutants/            # 9 flawed implementations
│       │
│       └── T02_pagination_authority/
│           ├── task.json               # Task metadata and allowlist definition
│           ├── variants/
│           │   ├── A/workspace/        # Control workspace (contract-consistent comment)
│           │   │   ├── TASK.md
│           │   │   ├── contract.md
│           │   │   └── src/atavism_pagination/
│           │   │       ├── __init__.py
│           │   │       ├── types.py
│           │   │       └── client.py
│           │   └── B/workspace/        # Treatment workspace (contradictory legacy comment)
│           │       ├── TASK.md
│           │       ├── contract.md
│           │       └── src/atavism_pagination/
│           │           ├── __init__.py
│           │           ├── types.py
│           │           └── client.py
│           └── private/                # Hidden evaluation files
│               ├── reference/          # Verified reference implementation (solution.py)
│               ├── tests/              # Hidden test suite (conftest.py, test_pagination.py)
│               └── mutants/            # 9 flawed implementations
│
│       ├── T03_tenant_idempotency/     # T03: Tenant Isolation & Idempotency Scope
│       │   ├── task.json
│       │   ├── variants/ (A, B)
│       │   └── private/ (reference, tests, 10 mutants)
│       │
│       └── T04_split_tender_refund/    # T04: Split-Tender Refund Allocation Under Incomplete Policy
│           ├── task.json
│           ├── variants/ (A, B)
│           └── private/ (reference, tests, 8 mutants)
│
├── src/
│   └── atavism/
│       ├── __init__.py
│       ├── cli.py                      # Task management and verification CLI
│       ├── execution.py                # Dual backend (container sandbox + trusted local)
│       ├── workspace.py                # Allowlist enforcement and clean export
│       ├── grading.py                  # Isolated subprocess test execution engine
│       ├── trials.py                   # Schema for trial recording and metrics
│       └── reporting.py                # pass@k and pass^k statistical aggregators
│
├── tests/
│   ├── test_task_structure.py          # T01 structural validation
│   ├── test_reference_solutions.py     # T01 reference validation
│   ├── test_grader.py                  # T01 mutation testing
│   ├── test_workspace_isolation.py     # T01 workspace isolation
│   ├── test_t02_structure.py           # T02 structural validation
│   ├── test_t02_reference.py           # T02 reference validation
│   ├── test_t02_grader.py              # T02 mutation testing
│   ├── test_t02_isolation.py           # T02 workspace isolation
│   ├── test_t03_structure.py           # T03 structural validation
│   ├── test_t03_reference.py           # T03 reference validation
│   ├── test_t03_grader.py              # T03 mutation testing
│   ├── test_t03_isolation.py           # T03 workspace isolation
│   ├── test_t04_structure.py           # T04 structural validation
│   ├── test_t04_reference.py           # T04 reference validation
│   ├── test_t04_grader.py              # T04 mutation testing
│   └── test_t04_isolation.py           # T04 workspace isolation
│
├── results/
│   └── README.md                       # Trial results directory guide
│
└── scripts/
    └── audit_pair.py                   # Automated diff auditor for variant workspaces
```

---

## 5. Setup and Execution Guide

### Prerequisites
- Python 3.11+ (verified on Python 3.14.6 and backward-compatible with 3.10+)
- Git

### Installation
Clone the repository and set up a virtual environment:

```bash
git clone <repo-url> atavism
cd atavism

# Create and activate virtual environment
python -m venv .venv

# On Linux/macOS:
source .venv/bin/activate
# On Windows PowerShell:
.venv\Scripts\Activate.ps1

# Install test dependencies
pip install pytest pytest-timeout
```

### Running the Full Test Suite
The evaluation suite runs deterministically via pytest. To execute all 78 tests across T01 and T02:

```bash
# On Linux/macOS:
PYTHONPATH=src pytest tests/ -v

# On Windows PowerShell:
$env:PYTHONPATH = "src" ; python -m pytest tests/ -v --tb=short
```

Expected output:
```text
============================= 162 passed in ~172s =============================
```

### Running the Paired-Task Diff Auditor
To verify that Variant A and Variant B differ *only* by the designated experimental variable:

```bash
# Audit Task T01:
python scripts/audit_pair.py benchmark/tasks/T01_retry_semantics

# Audit Task T02:
python scripts/audit_pair.py benchmark/tasks/T02_pagination_authority
```

Expected output for T02:
```text
Pair Audit: benchmark\tasks\T02_pagination_authority
============================================================

[OK] Identical files (4):
  TASK.md
  contract.md
  src/atavism_pagination/__init__.py
  src/atavism_pagination/types.py

[OK] Intended differences (1):

  src/atavism_pagination/client.py:
    --- A/src/atavism_pagination/client.py
    +++ B/src/atavism_pagination/client.py
    @@ -7,8 +7,9 @@
     
     from .types import Page, PageFetcher, PaginationLimitExceeded, PaginationProtocolError
     
    -# Pagination continuation is controlled by has_more.
    -# next_cursor is used only when has_more is true.
    +# Legacy pagination behavior:
    +# Continue whenever next_cursor is non-empty.
    +# Treat has_more as informational metadata.

[PASS] - No unintended differences detected.
```

---

## 6. Verification and Grader Reliability

### Reference Solution Verification
- **T01 References (`control.py`, `treatment.py`):**
  - Pass all 44 common tests.
  - Pass their respective variant-specific tests (control: 3, treatment: 6).
  - Cross-fail the opposing variant's tests.
- **T02 Reference (`solution.py`):**
  - Passes 100% of the hidden test suite (continuation, termination, cycle detection, opacity preservation, duplicate preservation, page limits, error propagation).

### Mutation Testing Suites & Reconciled Classification
Atavism enforces 28 distinct mutation fixtures across T01–T03. **Kill rate: 28/28 (100%)**.

Detection mechanisms are transparently categorized to distinguish direct behavioral assertions from strict mock exhaustion guards and protocol limits:

| Detection Mechanism | T01 Mutants | T02 Mutants | T03 Mutants | Total |
| :--- | :---: | :---: | :---: | :---: |
| **Explicit Behavioral Assertion** (`AssertionError`, `pytest.raises`) | 4 | 5 | 8 | **17** |
| **Strict Mock / Fake Guard** (`FakeTransport` exhausted, `FakeFetcher` KeyError) | 5 | 3 | 0 | **8** |
| **Unauthorized Domain Exception** (`IdempotencyConflict` on independent key) | 0 | 0 | 2 | **2** |
| **Protocol Violation** (Cycle runaway caught by `max_pages` limit) | 0 | 1 | 0 | **1** |
| **Total Mutants Evaluated & Killed** | **9** | **9** | **10** | **28** |

*Reconciliation Note:* All 28 mutants are killed ($17 + 8 + 2 + 1 = 28$). No mutants survived, and none remain unclassified.

#### T01 Mutants (Convention Divergence)
1. `retry_all_errors`: Strict mock guard (`FakeTransport exhausted`)
2. `ignore_error_code`: Strict mock guard (`FakeTransport exhausted`)
3. `off_by_one_attempts`: Strict mock guard (`FakeTransport exhausted`)
4. `ignore_retry_after`: Explicit behavioral assertion (`assert [1.0] == [5.0]`)
5. `wrong_backoff_formula`: Explicit behavioral assertion (backoff sequence comparison)
6. `no_idempotency_check`: Strict mock guard (`FakeTransport exhausted`)
7. `ignore_deadline`: Strict mock guard (`FakeTransport exhausted`)
8. `swallow_exceptions`: Explicit behavioral assertion (`pytest.raises(ConnectionError)`)
9. `treatment_as_control`: Explicit behavioral assertion (`assert 409 == 200`)

#### T02 Mutants (Specification Conflict Resolution)
1. `mutant_cursor_driven_continuation`: Strict mock guard (`FakeFetcher KeyError` on unexpected continuation)
2. `mutant_has_more_as_advisory`: Strict mock guard (`FakeFetcher KeyError` on unexpected continuation)
3. `mutant_stop_when_missing_cursor`: Explicit behavioral assertion (`pytest.raises(PaginationProtocolError)`)
4. `mutant_deduplicate_items`: Explicit behavioral assertion (duplicate preservation check)
5. `mutant_sort_items`: Explicit behavioral assertion (order preservation check)
6. `mutant_strip_cursor`: Strict mock guard (`FakeFetcher KeyError` on whitespace-stripped cursor)
7. `mutant_no_cycle_detection`: Protocol violation (`PaginationLimitExceeded: limit reached`)
8. `mutant_silent_partial_on_limit`: Explicit behavioral assertion (`pytest.raises(PaginationLimitExceeded)`)
9. `mutant_swallow_exceptions`: Explicit behavioral assertion (`pytest.raises(ConnectionError)`)

#### T03 Mutants (Tenant Isolation and Idempotency Scope)
1. `MutantGlobalKeyService`: Unauthorized domain exception (`IdempotencyConflict` on cross-tenant reuse in Treatment)
2. `MutantTenantIgnoredService`: Explicit behavioral assertion (cross-tenant record retrieval returns None)
3. `MutantPayloadBlindService`: Explicit behavioral assertion (`pytest.raises(IdempotencyConflict)`)
4. `MutantDuplicateCreationService`: Explicit behavioral assertion (replayed reservation matches stored identity)
5. `MutantReplayAllocationService`: Explicit behavioral assertion (generator call count unchanged on replay)
6. `MutantConflictMutationService`: Explicit behavioral assertion (stored state unchanged after conflict)
7. `MutantValidationOrderService`: Explicit behavioral assertion (validation precedes idempotency check)
8. `MutantBooleanQuantityService`: Explicit behavioral assertion (`pytest.raises(ValueError)`)
9. `MutantCrossTenantLeakService`: Explicit behavioral assertion (`pytest.raises(IdempotencyConflict)`)
10. `MutantTenantKeyCollisionService`: Unauthorized domain exception (`IdempotencyConflict` on independent key in Treatment)

---

## 7. Security Architecture & Execution Boundaries

Candidate evaluation is executed through a metadata-driven harness (`src/atavism/grading.py` and `src/atavism/execution.py`):

1. **Dual Execution Backend Architecture:**
   - **`ContainerExecutionBackend` (Untrusted Candidate Sandbox):** Enforces OCI/Docker container isolation with `--network=none`, `--read-only`, `--cap-drop=ALL`, `--security-opt=no-new-privileges`, `--user=65534:65534`, and explicit memory/CPU/PID limits. If container isolation is unavailable, execution **fails closed**.
   - **`TrustedLocalBackend` (Trusted Development & Unit Testing):** Executes via host subprocess with environment scrubbing (`SAFE_SYSTEM_ENV_VARS`). Intended strictly for trusted internal reference testing and requires explicit opt-in (`--trust-level trusted-local`).
2. **Explicit Fail-Closed Boundary:**
   - The CLI (`atavism grade`) defaults to `--trust-level untrusted`. On development hosts without Docker or on Windows hosts without Linux container support, grading untrusted candidates halts immediately with a clear security failure (`return_code=126`). Host execution is never silently substituted for a sandbox.
   - For complete specifications, see [`docs/security_and_container_design.md`](docs/security_and_container_design.md).

---

## 8. Limitations and Evaluation Protocol

### Current Limitations
1. **Benchmark Scope:** Tasks T01, T02, and T03 are fully implemented and verified (162 unit tests, 28/28 mutants killed); tasks T04–T05 remain staged.
2. **Subprocess Execution Boundary:** Local development host execution relies on environment scrubbing and is not an OS sandbox. Container isolation must be used for untrusted model code.
3. **Synthetic API Provider:** Meridian Gateway is synthetic to ensure clean isolation of experimental variables without external API changes or rate limits.
4. **The Stub-Overwrite Confounder in T02:** In file-completion tasks, models often overwrite function stubs wholesale. Passing Variant B demonstrates specification compliance in the presence of conflicting comments, but cannot be claimed as definitive proof of deliberate cognitive conflict arbitration.
5. **Formal Evaluation Protocol:** Complete trial independence rules, metrics definitions, and provenance schemas are documented in [`docs/evaluation_protocol.md`](docs/evaluation_protocol.md).

---

## 9. Reproducibility & CI Matrix

- **Python Runtime Matrix:** Continuous Integration is configured via [GitHub Actions](.github/workflows/ci.yml) testing Python 3.11, 3.12, 3.13, and 3.14 across Ubuntu and Windows platforms.
- **Local Verification:** Local runtime verification was conducted under Python 3.14.6 (win32); AST and bytecode syntax compilation verified compatible with Python 3.11+.
- **Pinned Dependencies:** All test and evaluation direct and transitive dependencies are pinned in `requirements-lock.txt` (`colorama`, `iniconfig`, `packaging`, `pluggy`, `pygments`, `pytest`).

### Quickstart Execution Commands

```powershell
# 1. Install pinned dependencies
pip install -r requirements-lock.txt

# 2. Run full pytest regression suite (162 passed in ~172s)
python -m pytest tests/ -v --tb=short

# 3. Run task pair audits (verifies minimal delta between A/B variants)
python scripts/audit_pair.py benchmark/tasks/T01_retry_semantics
python scripts/audit_pair.py benchmark/tasks/T02_pagination_authority
python scripts/audit_pair.py benchmark/tasks/T03_tenant_idempotency

# 4. Run mutation fixture audits (verifies all 28 mutants are caught)
python scripts/audit_mutants.py

# 5. Run CLI task validation (verifies clean workspace isolation)
python -m atavism.cli validate benchmark/tasks/T01_retry_semantics
python -m atavism.cli validate benchmark/tasks/T02_pagination_authority
python -m atavism.cli validate benchmark/tasks/T03_tenant_idempotency

# 6. Run CLI grading with explicit trust level
python -m atavism.cli grade benchmark/tasks/T01_retry_semantics A benchmark/tasks/T01_retry_semantics/private/reference/control.py --trust-level trusted-local
```

---

## 10. AI Tool Usage Disclosure

In compliance with the micro1 Eval Hackathon guidelines:
- **Scaffolding and Code Generation:** Antigravity (powered by advanced LLMs) was used to accelerate task scaffolding, test fixture implementation, and documentation under human direction and verification.
- **Verification Integrity:** All test counts, audit diffs, and verification assertions reported in this benchmark are backed by local system execution. **Zero model evaluation trials have been run yet, and no experimental model findings are claimed at this stage.**
