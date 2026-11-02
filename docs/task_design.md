# Atavism — Task Design Guide

## Principles

### 1. Explicit Contracts

Every requirement that the grader tests must be explicitly stated in the task's contract document. The grader must never expect behavior that was not communicated to the model.

### 2. Controlled Pairing

Each benchmark task consists of two variants designed to isolate a single experimental variable:

- **Control (A):** Represents standard, consistent, or conventional baseline behavior.
- **Treatment (B):** Introduces a controlled departure—either a deliberate deviation in the authoritative contract (e.g., T01's retry classification) or a source of conflicting implementation guidance (e.g., T02's legacy inline comment).

Both variants share identical environment, starter code interfaces, dependency profiles, and grading standards.

### 3. Minimal Difference

The treatment variant should differ from the control in exactly one designated location (the experimental variable). For instance:
- In **T01**, the difference is confined to `contract.md` (the status of 409 LEASE_BUSY).
- In **T02**, the difference is confined to `client.py` (an inline implementation comment contrasting contract adherence against legacy continuation heuristics).

### 4. Deterministic Grading

All tests must be deterministic. Use dependency injection (fake clocks, fake transports, fake sleepers, programmable fetchers) to eliminate non-determinism from timing, network sockets, or system state.

### 5. Grader Validation

- Every reference solution must pass its corresponding grader.
- Deliberately incorrect implementations (mutation fixtures) must fail relevant tests.
- Both validations must be verified before the task is considered complete.

## Task Structure

Each task directory follows this layout:

```text
T{nn}_{name}/
├── task.json               # Task metadata and allowlist definition
├── variants/
│   ├── A/workspace/        # Control variant model workspace
│   │   ├── TASK.md          # Task description & source hierarchy
│   │   ├── contract.md      # Provider contract
│   │   └── src/             # Starter package
│   └── B/workspace/        # Treatment variant model workspace
│       ├── TASK.md
│       ├── contract.md
│       └── src/
└── private/
    ├── reference/           # Reference implementation(s)
    ├── tests/               # Hidden test suites
    └── mutants/             # Deliberately flawed candidate implementations
```

## Benchmark Tasks Implemented

### T01 — Retry Semantics Under Provider-Specific Contracts
- **Research Dimension:** Convention Divergence
- **Experimental Variable:** HTTP 409 `LEASE_BUSY` retryability defined in `contract.md`.
- **Target Limitation:** AI coding models default to familiar HTTP retry conventions (never retrying 409) rather than adhering to provider-specific contracts.

### T02 — Pagination Continuation Under Conflicting Implementation Guidance
- **Research Dimension:** Specification Conflict Resolution
- **Experimental Variable:** Inline source code comment in `client.py` (contract-consistent in Variant A vs. contradictory legacy guidance in Variant B).
- **Target Limitation:** AI coding models prioritize nearby, informal, or legacy implementation comments over the authoritative API contract when deciding pagination continuation (`has_more` vs. `next_cursor`).

## File Allowlist for Workspace Export

Only these files may be included in a model workspace export:

- `TASK.md`
- `contract.md`
- `src/**/*.py`

Never include: reference solutions, test files, grader code, mutation fixtures, `task.json`, or any file from `private/`.
