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
| **Semantic Composition** | Preserving multiple interacting technical requirements simultaneously (e.g., deadlines, backoff, idempotency). | Staged |
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
├── src/
│   └── atavism/
│       ├── __init__.py
│       ├── cli.py                      # Task management and verification CLI
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
│   └── test_t02_isolation.py           # T02 workspace isolation
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
============================= 78 passed in ~27s =============================
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

### Mutation Testing Suites
Each task includes 9 distinct mutation fixtures verifying that faulty candidates are caught by the grader:

#### T01 Mutants (Convention Divergence)
1. `retry_all_errors` (retries any $\ge 400$)
2. `ignore_error_code` (ignores error code string)
3. `off_by_one_attempts` (max_attempts off-by-one)
4. `ignore_retry_after` (ignores Retry-After header)
5. `wrong_backoff_formula` (incorrect exponent)
6. `no_idempotency_check` (retries unsafe methods without key)
7. `ignore_deadline` (fails to budget time)
8. `swallow_exceptions` (swallows transport errors)
9. `treatment_as_control` (uses control behavior in treatment)

#### T02 Mutants (Specification Conflict Resolution)
1. `mutant_cursor_driven_continuation` (follows misleading legacy comment; continues if next_cursor is present)
2. `mutant_has_more_as_advisory` (treats has_more as advisory; continues on next_cursor even if has_more=False)
3. `mutant_stop_when_missing_cursor` (stops quietly when next_cursor is missing instead of raising error)
4. `mutant_deduplicate_items` (deduplicates records during aggregation)
5. `mutant_sort_items` (reorders/sorts records)
6. `mutant_strip_cursor` (modifies opaque cursor by stripping whitespace)
7. `mutant_no_cycle_detection` (fails to detect repeated cursors)
8. `mutant_silent_partial_on_limit` (silently returns partial results on page limit)
9. `mutant_swallow_exceptions` (swallows fetcher exceptions)

---

## 7. Security Architecture & Execution Boundaries

Candidate evaluation is executed through a metadata-driven harness (`src/atavism/grading.py`):

1. **Local Subprocess Sandbox (Development & Verification):**
   - Applies strict environment scrubbing via allowlist (`SAFE_SYSTEM_ENV_VARS`), stripping API keys, tokens, SSH vars, and cloud credentials.
   - Enforces a hard execution timeout (default 60s) and working-directory sandboxing.
   - *Security Notice:* Environment scrubbing prevents credential leakage but does **not** provide kernel-level filesystem or network virtualization.
2. **Containerized Jail Specification (Untrusted Candidate Trials):**
   - Detailed in [`docs/security_and_container_design.md`](docs/security_and_container_design.md).
   - Specifies `--network none`, `--read-only`, unprivileged user (`nobody:nogroup`), capability dropping (`--cap-drop=ALL`), and cgroup resource limits.

---

## 8. Limitations and Known Methodological Considerations

### Current Limitations
1. **Benchmark Scope:** Tasks T01 and T02 are fully implemented and hardened; tasks T03–T05 remain staged.
2. **Subprocess Execution Boundary:** Candidate evaluation currently uses process-level subprocess isolation with environment scrubbing; containerized sandboxing (`--network none`) is required for untrusted model execution.
3. **Synthetic API Provider:** Meridian Gateway is synthetic to ensure clean isolation of experimental variables without external API changes or rate limits.
4. **The Stub-Overwrite Confounder in T02:** In file-completion tasks, models often overwrite function stubs wholesale. Passing Variant B demonstrates specification compliance in the presence of conflicting comments, but cannot be claimed as definitive proof of deliberate cognitive conflict arbitration. The primary valid metric is the cross-variant delta ($\text{PassRate}_A - \text{PassRate}_B$).

### Next Steps
1. **Implement Task T03:** Semantic Composition (e.g. multi-part SSE stream decoding with custom event boundary rules).
2. **Conduct Model Evaluation Trials:** Execute multi-trial evaluations (3–5 trials per variant) across frontier models.
3. **Statistical Analysis:** Compute pass@1, pass@k, and control-versus-treatment delta $\Delta = \text{pass}(B) - \text{pass}(A)$.

---

## 9. Reproducibility & CI Matrix

- **Python Runtime Matrix:** Continuous Integration is configured via [GitHub Actions](.github/workflows/ci.yml) testing Python 3.11, 3.12, 3.13, and 3.14 across Ubuntu and Windows platforms.
- **Local Verification:** Local runtime verification was conducted under Python 3.14.6 (win32); AST and bytecode syntax compilation verified compatible with Python 3.11+.
- **Pinned Dependencies:** All test and evaluation dependencies are pinned in `requirements-lock.txt`.

### Quickstart Execution Commands

```powershell
# 1. Install pinned dependencies
pip install -r requirements-lock.txt

# 2. Run full pytest regression suite
$env:PYTHONPATH = "src"
python -m pytest tests/ -v --tb=short

# 3. Run task pair audits (verifies minimal delta between A/B variants)
python scripts/audit_pair.py benchmark/tasks/T01_retry_semantics
python scripts/audit_pair.py benchmark/tasks/T02_pagination_authority

# 4. Run mutation fixture audits (verifies all 18 mutants are caught)
python scripts/audit_mutants.py

# 5. Run CLI task validation
python -m atavism.cli validate benchmark/tasks/T01_retry_semantics
python -m atavism.cli validate benchmark/tasks/T02_pagination_authority
```

---

## 10. AI Tool Usage Disclosure

In compliance with the micro1 Eval Hackathon guidelines:
- **Scaffolding and Code Generation:** Antigravity (powered by advanced LLMs) was used to accelerate task scaffolding, test fixture implementation, and documentation under human direction and verification.
- **Verification Integrity:** All test counts, audit diffs, and verification assertions reported in this benchmark are backed by local system execution. **Zero model evaluation trials have been run yet, and no experimental model findings are claimed at this stage.**
