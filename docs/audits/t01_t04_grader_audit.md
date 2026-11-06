# Atavism — Comprehensive Grader and Mutation Audit (T01–T04)

**Audit Date:** 2026-11-06  
**Auditor:** Senior Infrastructure Engineer, Benchmark Architect & Independent Technical Auditor  
**Tasks Audited:** T01, T02, T03, T04  
**Scope:** Reference implementations, alternative positive controls, cross-variant discrimination, diagnostic category attribution, and mutation fixture rejection mechanisms.  

---

## 1. Reference Implementation Verification

Every primary reference solution and alternative positive control was graded against its target variant using the isolated metadata-driven grading harness:

| Task | Candidate File | Variant | Target Status | Tests Total | Tests Passed | Failed | Errors |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **T01** | `control.py` | A | **PASS** | 24 | 24 | 0 | 0 |
| **T01** | `treatment.py` | B | **PASS** | 24 | 24 | 0 | 0 |
| **T02** | `solution.py` | A | **PASS** | 31 | 31 | 0 | 0 |
| **T02** | `solution.py` | B | **PASS** | 31 | 31 | 0 | 0 |
| **T03** | `control.py` | A | **PASS** | 61 | 61 | 0 | 0 |
| **T03** | `treatment.py` | B | **PASS** | 62 | 62 | 0 | 0 |
| **T03** | `alt_control.py` | A | **PASS** | 61 | 61 | 0 | 0 |
| **T03** | `alt_treatment.py` | B | **PASS** | 62 | 62 | 0 | 0 |
| **T04** | `control.py` | A | **PASS** | 23 | 23 | 0 | 0 |
| **T04** | `treatment.py` | B | **PASS** | 27 | 27 | 0 | 0 |
| **T04** | `alt_control.py` | A | **PASS** | 23 | 23 | 0 | 0 |
| **T04** | `alt_treatment.py` | B | **PASS** | 27 | 27 | 0 | 0 |

---

## 2. Cross-Variant Discrimination Audit

Cross-variant tests evaluate whether the graders reject implementations that satisfy the opposing variant's semantics:

| Task | Candidate | Evaluated Variant | Expected | Actual | Rejecting Category | Failing Tests Count |
| :---: | :--- | :---: | :---: | :---: | :--- | :---: |
| **T01** | `control.py` | B | **FAIL** | **FAIL** | `treatment` | 5 |
| **T01** | `treatment.py` | A | **FAIL** | **FAIL** | `control` | 5 |
| **T03** | `control.py` | B | **FAIL** | **FAIL** | `cross_tenant_key_scope` | 5 |
| **T03** | `treatment.py` | A | **FAIL** | **FAIL** | `cross_tenant_key_scope` | 5 |
| **T04** | `control.py` | B | **FAIL** | **FAIL** | `treatment_policy` | 2 |
| **T04** | `treatment.py` | A | **FAIL** | **FAIL** | `control_policy` | 4 |

**Observations:**
- In all cross-variant evaluations, **common requirement categories pass with 100% scores**.
- Failure occurs **strictly** within the targeted variant-specific diagnostic category (`control_policy`, `treatment_policy`, or `cross_tenant_key_scope`).
- This proves zero coupling between common baseline checks and variant-specific discrimination logic.

---

## 3. Mutation Fixture Coverage & Rejection Reconciliation

All 36 repository mutants across T01–T04 were audited using [`scripts/audit_mutants.py`](file:///d:/Micro1%20Eval%20Hackathon/atavism/scripts/audit_mutants.py).
- **Total Mutants Evaluated:** 36
- **Total Mutants Killed:** 36 (100%)
- **Surviving Mutants:** 0

### Reconciled Failure Mechanisms

Rather than treating all killed mutants as equivalent evidence, failures are classified by exact rejection mechanism:

```
+-----------------------------------------------------------------------------+
|                         MUTATION RECONCILIATION SUMMARY                      |
+-----------------------------------+-------+---------------------------------+
| Detection Mechanism               | Count | Primary Tasks / Examples        |
+-----------------------------------+-------+---------------------------------+
| 1. Explicit behavioral assertion  |  23   | T01 (backoff, retry-after),     |
|                                   |       | T02 (dedup, sort, stop-cursor), |
|                                   |       | T03 (tenant ignore, validation),|
|                                   |       | T04 (silent defaults, balances) |
+-----------------------------------+-------+---------------------------------+
| 2. Strict mock / fake guard       |   8   | T01 FakeTransport exhaustion,   |
|                                   |       | T02 FakeFetcher cursor check    |
+-----------------------------------+-------+---------------------------------+
| 3. Unauthorized domain exception  |   3   | T03 IdempotencyConflict leak,   |
|                                   |       | T04 False uncertainty error     |
+-----------------------------------+-------+---------------------------------+
| 4. Protocol violation             |   2   | T02 PaginationLimitExceeded,    |
|                                   |       | T04 Blanket NotImplementedError |
+-----------------------------------+-------+---------------------------------+
| TOTAL KILLED                      |  36   | 23 + 8 + 3 + 2 = 36 (Exact)     |
+-----------------------------------+-------+---------------------------------+
```

### Analysis of Mock Guard vs. Explicit Assertion
- 8 mutants (5 in T01, 3 in T02) are rejected by strict fake/mock guards (`FakeTransport exhausted`, `Unexpected cursor passed to FakeFetcher`).
- *Methodological Scrutiny:* When a mock exhausts its pre-programmed response list or detects an unexpected token, it stops execution immediately. While this effectively catches off-by-one loops or premature retries, it is a structural guard rather than an explicit post-execution assertion.
- *Remediation Status:* In T01 and T02, these guards are backed by explicit tests in `test_grader.py` and `test_t02_grader.py`.

---

## 4. Grader Robustness & Boundary Coverage Analysis

1. **Accidental Exceptions:**
   - In T04 `test_treatment_policy.py`, tests probe whether an unconfigured candidate silently returns a concrete allocation. If the candidate raises `RefundError`, `NotImplementedError`, or a custom domain error, the test catches the exception and succeeds (because failing closed is the expected uncertainty-handling behavior).
2. **Architecture Agnosticism:**
   - Graders do not inspect AST or private class attributes.
   - Graders invoke solely the public API defined in `task.json`:
     - T01: `send_with_retry`
     - T02: `collect_all_items`
     - T03: `ReservationService.create_reservation`, `get_reservation`
     - T04: `RefundService.process_refund`
   - Alternative positive controls featuring completely different internal architectures (functional decomposition vs. strategy pattern vs. imperative loops) all pass 100%.
3. **Monetary & Numeric Precision:**
   - T04 strictly uses `decimal.Decimal` with 2-decimal-place cents. Binary floats are rejected.
   - T03 strictly rejects `bool` (`True`/`False`) as integer quantities.

