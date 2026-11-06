# Atavism — Reproducibility and CI Audit

**Audit Date:** 2026-11-06  
**Auditor:** Senior Infrastructure Engineer & Reproducibility Auditor  
**Target:** Dependency manifests, CI workflows, determinism controls, and clean export verification.  

---

## 1. Dependency and Environment Reproducibility

### 1.1 Dependency Manifests
- **Runtime Dependencies:** Zero third-party runtime dependencies. Atavism core (`src/atavism/`) and candidate domain packages (`atavism_retry`, `atavism_pagination`, `atavism_reservation`, `atavism_refund`) rely strictly on the Python Standard Library (`dataclasses`, `decimal`, `enum`, `json`, `pathlib`, `subprocess`, `tempfile`, `xml.etree`).
- **Evaluation / Dev Dependencies:** Pinned in [`requirements-lock.txt`](file:///d:/Micro1%20Eval%20Hackathon/atavism/requirements-lock.txt):
  ```text
  colorama==0.4.6; sys_platform == "win32"
  iniconfig==2.3.0
  packaging==26.3
  pluggy==1.6.0
  pygments==2.21.0
  pytest==9.1.1
  ```
- **Lockfile Completeness:** Verified. Transitive dependencies are fully pinned with exact version numbers and environment markers.

### 1.2 Python Version Compatibility
- Declared: `requires-python = ">=3.11"` in `pyproject.toml`.
- Locally Verified: Python 3.14.6 (Windows 11).
- CI Matrix: Automated matrix testing across Python 3.11, 3.12, 3.13, and 3.14 on both Ubuntu and Windows.

---

## 2. CI Pipeline Audit (`.github/workflows/ci.yml`)

### 2.1 Workflow Matrix
- **Operating Systems:** `ubuntu-latest`, `windows-latest` (cross-platform verification).
- **Python Versions:** `3.11`, `3.12`, `3.13`, `3.14` (8 concurrent matrix jobs).

### 2.2 Execution Steps Verified
1. **Checkout:** `actions/checkout@v4`
2. **Setup Python:** `actions/setup-python@v5` with pip caching.
3. **Dependency Installation:** `pip install -r requirements-lock.txt`
4. **Test Suite:** `python -m pytest tests/ -v --tb=short` (executes all 203 repository tests).
5. **Task Pair Audits:** Automated `scripts/audit_pair.py` for T01, T02, T03, and T04.
6. **Mutation Audits:** `python scripts/audit_mutants.py` verifying all 36 mutants killed.
7. **CLI Task Validations:** `python -m atavism.cli validate` for T01, T02, T03, and T04.

*Audit Remediation:* Added missing T04 pair audit and CLI validation steps to `.github/workflows/ci.yml`.

---

## 3. Determinism & Randomness Analysis

1. **Temporal Determinism:**
   - In T01 (Retry Semantics), timing is driven by injected `Clock` and `Sleeper` interfaces. Zero `time.sleep()` calls are used. Tests run in sub-second deterministic virtual time.
2. **Numerical Determinism:**
   - In T04 (Refund Allocation), monetary arithmetic is executed exclusively via Python `Decimal` with standard 2-decimal-place rounding (`Decimal('0.01')`). Binary floating-point arithmetic is strictly prohibited.
3. **Data Structure Traversal Determinism:**
   - Environment scrubbing injects `PYTHONHASHSEED="0"` into candidate subprocesses where needed, and collections are explicitly sorted before serialization.
4. **Filesystem Cleanliness:**
   - Grader runs in ephemeral temporary directories (`tempfile.TemporaryDirectory`) cleaned immediately on context manager exit.

---

## 4. Workspace Export and Information Isolation

Workspace exports for all four tasks were evaluated via `atavism.workspace.export_workspace`:
- **Allowed Files Exported:** `TASK.md`, `contract.md`, `src/**/*.py` (exactly 5 files per variant).
- **Leakage Check:** 0 private files (`solution.py`, `control.py`, `treatment.py`, `conftest.py`, `test_*.py`, `mutants/`, `task.json`) leaked.
- **Export Integrity:** Passing allowlist validation with 0 disallowed files across all 8 variants (T01-A, T01-B, T02-A, T02-B, T03-A, T03-B, T04-A, T04-B).

