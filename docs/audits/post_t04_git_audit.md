# Atavism — Post-T04 Git & Repository Baseline Audit

**Audit Date:** 2026-11-06  
**Auditor:** Senior Infrastructure Engineer, Security Reviewer & Independent Technical Auditor  
**Scope:** Repository structure, Git working tree, commit baseline, CI configuration, and dependency manifests.  

---

## 1. Baseline Git State Identification

| Metric | Verified Value | Evidence |
| :--- | :--- | :--- |
| **Current Branch** | `main` | `git status` output (`On branch main`) |
| **Current HEAD Commit** | `ad4edf811142f75625eb0fdc74e3aa61efef91f0` | `git rev-parse HEAD` |
| **Parent Commit** | `623187b3d8eb3305f1f69588eb30239c7744d4d6` | `git log -n 2 --oneline` |
| **Working Tree Status** | Clean (0 modified, 0 untracked files) | `git status -s` |
| **T04 Commit Status** | **Committed** in `ad4edf8` | `git show --stat ad4edf8` |

---

## 2. Audit of Commit `ad4edf8` (`feat: implement T04 split-tender refund benchmark`)

Inspection of commit `ad4edf8` reveals 33 files changed (2,747 insertions, 6 deletions):
1. **Task Artifacts:** Complete directory structure for `benchmark/tasks/T04_split_tender_refund/` including `task.json`, Variant A and Variant B workspaces, private references (`control.py`, `treatment.py`, `alt_control.py`, `alt_treatment.py`), private tests (`common/`, `control/`, `treatment/`), and 8 mutation fixtures.
2. **Audit Scripts:** [`scripts/audit_mutants.py`](file:///d:/Micro1%20Eval%20Hackathon/atavism/scripts/audit_mutants.py) updated with `audit_t04_mutants()` and 36-mutant reconciliation.
3. **Repository Tests:** Added 4 new test suites in `tests/`:
   - `test_t04_structure.py` (11 tests)
   - `test_t04_isolation.py` (14 tests)
   - `test_t04_reference.py` (6 tests)
   - `test_t04_grader.py` (8 tests)
4. **Research Documentation:** Created [`docs/T04_research_design.md`](file:///d:/Micro1%20Eval%20Hackathon/atavism/docs/T04_research_design.md), updated [`docs/task_design.md`](file:///d:/Micro1%20Eval%20Hackathon/atavism/docs/task_design.md), [`docs/evaluation_protocol.md`](file:///d:/Micro1%20Eval%20Hackathon/atavism/docs/evaluation_protocol.md), and [`README.md`](file:///d:/Micro1%20Eval%20Hackathon/atavism/README.md).
5. **Frozen Tasks Preservation:** `git diff 623187b..ad4edf8 -- benchmark/tasks/T01* benchmark/tasks/T02* benchmark/tasks/T03*` returned 0 changes. T01, T02, and T03 were strictly preserved.

---

## 3. Discrepancy & Gap Analysis

### 3.1 CI Workflow Omission (`.github/workflows/ci.yml`)
- **Finding:** In `.github/workflows/ci.yml`, the `Run Task Pair Audits` step and `Run CLI Task Validations` step enumerate T01, T02, and T03, but **omit T04**:
  ```yaml
  # Current .github/workflows/ci.yml lines 44-46 and 58-60:
  python scripts/audit_pair.py benchmark/tasks/T01_retry_semantics
  python scripts/audit_pair.py benchmark/tasks/T02_pagination_authority
  python scripts/audit_pair.py benchmark/tasks/T03_tenant_idempotency
  # OMISSION: T04 is not audited in CI pair step or CLI validation step!
  ```
- **Risk:** Pull requests and CI runs on GitHub Actions will not automatically fail if T04 workspace pairing or CLI validation breaks.
- **Remediation:** Update `.github/workflows/ci.yml` to include:
  ```yaml
  python scripts/audit_pair.py benchmark/tasks/T04_split_tender_refund
  python -m atavism.cli validate benchmark/tasks/T04_split_tender_refund
  ```

### 3.2 Pytest Root Collection Configuration (`pyproject.toml`)
- **Finding:** `pyproject.toml` sets `testpaths = ["tests", "benchmark"]`.
- **Behavior:** Executing bare `pytest` triggers collection in `benchmark/**/private/tests/`, which fails because candidate modules (`atavism_retry`, `atavism_pagination`, etc.) are ephemeral candidate workspaces, not root packages.
- **Operational Reality:** All CI runs and documented procedures execute `python -m pytest tests/`, which targets `tests/` explicitly and passes 100% (203/203 tests).

---

## 4. Working Tree & Commit Recommendations

Per Non-Negotiable Rule 10, no automatic commits or remote changes will be executed.
Recommended staging upon completion of audit updates:
1. `docs/audits/*.md`
2. `.github/workflows/ci.yml` (adding T04 pair and CLI steps)
3. `docs/evaluation_protocol.md`
4. `docs/T05_research_design.md`

