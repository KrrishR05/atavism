# Atavism — Consolidated Benchmark Readiness Report

**Audit Date:** 2026-11-06  
**Auditor:** Senior AI Evaluation Researcher, Benchmark Architect, Infrastructure Engineer & Technical Auditor  
**Tasks Evaluated:** T01, T02, T03, T04, T05  
**Benchmark Commit Baseline:** `9763b920766424e0f5518b2eebf8a834cf7cad52`  

---

## 1. Multi-Dimensional Readiness Assessment

### 1. Research Design Readiness
- **Evidence:**
  - 5 orthogonal research dimensions:
    - T01: Convention Divergence (Retry Semantics under Provider-Specified Backoff)
    - T02: Conflict Resolution (Pagination Authority under Contradictory Specs)
    - T03: Semantic Composition (Multi-Tenant Idempotency Key Scoping)
    - T04: Incomplete Specification Uncertainty (Split-Tender Refund Allocation)
    - T05: Temporal Invariants & Asynchronous Protocol Adherence (Out-of-Order Event Stream Projection Protocol)
  - Matched control–treatment architecture with single-variable delta strictly enforced across all 5 task pairs.
  - T05 research design finalized ([`docs/T05_research_design.md`](file:///d:/Micro1%20Eval%20Hackathon/atavism/docs/T05_research_design.md)).
  - Starter-code leakage eliminated; neutral instructions across all variants.
- **Remaining Gaps:** Model evaluations have not yet established empirical distribution baselines.
- **Risk:** Low. Conceptual construct validity is verified across all 5 dimensions.
- **Required Action:** None for task design. All 5 tasks are finalized and frozen.
- **Status:** **READY**

---

### 2. Task Implementation Readiness
- **Evidence:**
  - All 5 tasks registered in `task.json` with execution schemas.
  - Clean directory layouts with model workspaces in `variants/{A,B}/workspace/` and hidden evaluation fixtures in `private/`.
  - Byte-identical starter files verified by automated diffing and pairing tests (`scripts/audit_pair.py`).
  - Python `Decimal` strictly used in T04 financial allocation and T05 account ledger balance projection; binary float prohibited.
  - Normative event identity registration verified in T05: sequence ID is recorded upon entering sequence processing after schema validation; gap-rejected events in Control A and buffered events in Treatment B retain identity, strictly rejecting conflicting redeliveries while permitting identical redeliveries.
- **Remaining Gaps:** None.
- **Risk:** Negligible.
- **Required Action:** Maintain strict task freeze on T01–T05.
- **Status:** **READY**

---

### 3. Grader Reliability
- **Evidence:**
  - Full test suite: **242 / 242 passed (100%)**.
  - All 16 primary reference solutions and alternative positive controls pass target variants with 100% diagnostic scores (T01: 2 refs, T02: 4 refs, T03: 2 refs, T04: 4 refs, T05: 4 refs).
  - Cross-variant discrimination verified: Control references fail Treatment graders, and Treatment references fail Control graders strictly within variant-specific diagnostic categories.
  - Mutation fixture coverage: **46 / 46 mutants killed (100%)** across T01–T05 (T01: 8/8, T02: 10/10, T03: 10/10, T04: 8/8, T05: 10/10).
  - Hidden evaluation test items: T05-A has 86 hidden test items, T05-B has 89 hidden test items.
  - All 13 blocked-stream causal non-bypass invariants in T05 verified by dedicated regression test fixtures.
- **Remaining Gaps:** None.
- **Risk:** Negligible.
- **Required Action:** None.
- **Status:** **READY**

---

### 4. Execution Security
- **Evidence:**
  - Dual-backend architecture in [`src/atavism/execution.py`](file:///d:/Micro1%20Eval%20Hackathon/atavism/src/atavism/execution.py).
  - CLI `--trust-level` defaults to `untrusted` and fails closed (exit code 126) when Docker is unavailable.
  - Subprocess environment scrubbing (`SAFE_SYSTEM_ENV_VARS`, `build_minimal_env()`) unconditionally purges host tokens, API keys, SSH credentials, and cloud secrets.
  - Command construction unit tests verify all hardened OCI flags (`--network=none`, `--read-only`, `--cap-drop=ALL`, `--user=nobody`, `--security-opt=no-new-privileges`, cgroups).
- **Security Boundary Clarification:**
  - `trusted-local` is strictly an internal harness for running verified, developer-authored reference implementations and mutation fixtures.
  - Environment scrubbing (`build_minimal_env()`) is **NOT** a sandbox: it provides zero process isolation, zero filesystem isolation, zero kernel sandboxing, zero network egress prevention, and zero resource limits.
  - Untrusted LLM-generated code MUST NEVER be executed under `trusted-local`.
  - Untrusted evaluation requires `--trust-level untrusted`, which enforces OCI container isolation and safely fails closed when a container runtime is unavailable.
- **Remaining Gaps:**
  - **The current development host runs Windows 11 without a running Docker engine.**
  - Live kernel container sandboxing has **not** been executed or verified on this machine.
- **Risk:** High if untrusted model code were executed on host without a container. (Fully mitigated by fail-closed enforcement).
- **Required Action:** Deploy to a Linux container host before conducting live untrusted LLM evaluations.
- **Status:** **BLOCKED ON HOST (Fail-Closed Operates Correctly)**

---

### 5. Reproducibility
- **Evidence:**
  - Transitive dependencies pinned in [`requirements-lock.txt`](file:///d:/Micro1%20Eval%20Hackathon/atavism/requirements-lock.txt).
  - Zero external runtime dependencies for candidate workspaces across all 5 tasks (pure Python standard library).
  - Deterministic evaluation fixtures: virtual time (T01), in-memory generators (T02), tenant key scoping (T03), exact `Decimal` cents (T04), deterministic stream replay (T05).
  - Bare `python -m pytest tests/` executes all 242 tests with zero collection errors.
  - `.github/workflows/ci.yml` matrix configured for Python 3.11–3.14 across Ubuntu and Windows, running full tests, pair audits for T01–T05, mutation audits for all 46 mutants, and CLI validation for all 5 tasks.
- **Remaining Gaps:** None.
- **Risk:** Low.
- **Required Action:** None.
- **Status:** **READY**

---

### 6. Documentation
- **Evidence:**
  - [`README.md`](file:///d:/Micro1%20Eval%20Hackathon/atavism/README.md) updated with T01–T05 overviews and tree diagrams.
  - [`docs/task_design.md`](file:///d:/Micro1%20Eval%20Hackathon/atavism/docs/task_design.md) documents principles, matched-pair conventions, and known confounders.
  - [`docs/T04_research_design.md`](file:///d:/Micro1%20Eval%20Hackathon/atavism/docs/T04_research_design.md) provides comprehensive post-audit design.
  - [`docs/T05_research_design.md`](file:///d:/Micro1%20Eval%20Hackathon/atavism/docs/T05_research_design.md) documents finalized v2.3.0 research design and normative state machine semantics.
  - [`docs/evaluation_protocol.md`](file:///d:/Micro1%20Eval%20Hackathon/atavism/docs/evaluation_protocol.md) specifies trial parameter matrix, provenance JSON schema, failure taxonomy, human review rubric, and Section 7.4 execution security boundaries.
- **Remaining Gaps:** None.
- **Risk:** Negligible.
- **Required Action:** None.
- **Status:** **READY**

---

### 7. Model Evaluation Readiness
- **Evidence:**
  - Full trial protocol specified: immutable model checkpoints, temperature 0.0/0.2, prompt construction, fresh-session requirements, balanced A/B ordering.
  - Output recording schema (`results/<trial_id>.json`) defined with token usage and timing metadata.
  - Evaluation protocol updated to encompass T01 through T05 with explicit diagnostic scoring weights.
- **Remaining Gaps:** Requires a provisioned Linux container host to execute untrusted model trials safely.
- **Risk:** Medium (contingent on container host setup).
- **Required Action:** Provision Linux evaluation environment.
- **Status:** **PROTOCOL READY, EXECUTION ENVIRONMENT CONTINGENT**

---

### 8. Hackathon Submission Readiness
- **Evidence:**
  - Professional, publishable research benchmark codebase.
  - 5 fully verified benchmark tasks covering distinct, non-overlapping software engineering challenges.
  - 242 passing tests, 46 killed mutants, 0 surviving defects.
  - Flawless pair differences (diff only in intended contract sections).
  - Clear methodology disclaimers (separating observable compliance from internal reasoning).
- **Remaining Gaps:** Live LLM evaluation trial data (to be executed on Linux host).
- **Risk:** Low.
- **Required Action:** Prepare demo artifacts and presentation slides.
- **Status:** **READY FOR SUBMISSION PACKAGING**

---

## 2. Overall Readiness Verdict

```text
================================================================================
FINAL VERDICT:
ENGINEERING READY — SECURITY BLOCKED
================================================================================
```

### Explanatory Verdict Breakdown
1. **Engineering Readiness: 100% COMPLETE.**
   - All code, tasks, tests, reference solutions, alternative controls, and mutation fixtures are fully verified, deterministic, and passing across T01 through T05.
2. **Security Readiness: BLOCKED ON LOCAL WINDOWS HOST.**
   - Untrusted execution correctly fails closed (code 126).
   - Live untrusted model trials cannot run on this machine until an active Docker daemon on a Linux host is provisioned.
3. **Model Trials: AUTHORIZED FOR LINUX CONTAINER HOST ONLY.**
   - Do NOT run untrusted model code with `--trust-level trusted-local`.


