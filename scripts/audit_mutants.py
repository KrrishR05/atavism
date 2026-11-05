"""Audit all mutation fixtures for T01 and T02.

Executes each mutant against the test suite, records killed/surviving status,
the exact test that caught it, and the rejection reason.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from atavism.grading import grade_candidate

ROOT = Path(__file__).resolve().parent.parent
T01_DIR = ROOT / "benchmark" / "tasks" / "T01_retry_semantics"
T02_DIR = ROOT / "benchmark" / "tasks" / "T02_pagination_authority"
T03_DIR = ROOT / "benchmark" / "tasks" / "T03_tenant_idempotency"


def audit_t01_mutants() -> list[dict[str, object]]:
    mutants_path = T01_DIR / "private" / "mutants" / "__init__.py"
    code = mutants_path.read_text(encoding="utf-8")

    mutants = [
        ("mutant_retry_all_errors", "Retries all 4xx/5xx regardless of status/code"),
        ("mutant_ignore_error_code", "Ignores error_code, only checks HTTP status"),
        ("mutant_off_by_one_attempts", "Allows max_attempts + 1 attempts (off-by-one)"),
        ("mutant_ignore_retry_after", "Ignores Retry-After header"),
        ("mutant_wrong_backoff", "Uses 2^retry instead of 2^(retry-1)"),
        ("mutant_no_idempotency_check", "Retries unsafe methods without Idempotency-Key"),
        ("mutant_ignore_deadline", "Never enforces overall timeout deadline"),
        ("mutant_swallow_exceptions", "Catches and swallows transport exceptions"),
        ("mutant_treatment_as_control", "Omits 409 LEASE_BUSY from retryable set in treatment"),
    ]

    results = []
    for name, desc in mutants:
        with tempfile.TemporaryDirectory(prefix=f"t01_mut_{name}_") as td:
            cand = Path(td) / "client.py"
            cand.write_text(
                f"{code}\n\n"
                f"def send_with_retry(request, transport, policy, *, clock, sleep):\n"
                f"    return {name}(request, transport, policy, clock=clock, sleep=sleep)\n",
                encoding="utf-8",
            )
            test_paths = (
                [T01_DIR / "private" / "tests" / "treatment"]
                if name == "mutant_treatment_as_control"
                else [T01_DIR / "private" / "tests" / "common"]
            )
            res = grade_candidate(
                cand,
                T01_DIR / "variants" / "A" / "workspace" / "src" / "atavism_retry" / "types.py",
                test_paths,
                T01_DIR / "private" / "tests" / "conftest.py",
                package_name="atavism_retry",
            )
            first_fail_test = "None"
            first_fail_reason = "None"
            if res.failure_reasons:
                first_key = list(res.failure_reasons.keys())[0]
                first_fail_test = first_key.split("::")[-1]
                first_fail_reason = res.failure_reasons[first_key].splitlines()[0]

            results.append({
                "mutant": name,
                "description": desc,
                "killed": not res.passed,
                "failed_tests_count": res.failed_tests,
                "first_rejecting_test": first_fail_test,
                "rejection_reason": first_fail_reason,
            })
    return results


def audit_t02_mutants() -> list[dict[str, object]]:
    mutants_path = T02_DIR / "private" / "mutants" / "__init__.py"
    code = mutants_path.read_text(encoding="utf-8")

    mutants = [
        ("mutant_cursor_driven_continuation", "Continues when next_cursor non-empty, ignores has_more"),
        ("mutant_has_more_as_advisory", "Treats has_more as advisory; continues if cursor present"),
        ("mutant_stop_when_missing_cursor", "Silently returns partial on missing cursor instead of raising error"),
        ("mutant_deduplicate_items", "Deduplicates records before returning"),
        ("mutant_sort_items", "Sorts items before returning"),
        ("mutant_strip_cursor", "Strips whitespace from opaque cursor token"),
        ("mutant_no_cycle_detection", "Fails to track cursors and detect cycles"),
        ("mutant_silent_partial_on_limit", "Silently returns partial data on page limit instead of raising error"),
        ("mutant_swallow_exceptions", "Swallows fetcher exceptions"),
    ]

    results = []
    for name, desc in mutants:
        with tempfile.TemporaryDirectory(prefix=f"t02_mut_{name}_") as td:
            cand = Path(td) / "client.py"
            cand.write_text(
                f"{code}\n\n"
                f"def collect_all_items(fetch_page, *, initial_cursor=None, max_pages=100):\n"
                f"    return {name}(fetch_page, initial_cursor=initial_cursor, max_pages=max_pages)\n",
                encoding="utf-8",
            )
            res = grade_candidate(
                cand,
                T02_DIR / "variants" / "A" / "workspace" / "src" / "atavism_pagination" / "types.py",
                [T02_DIR / "private" / "tests" / "test_pagination.py"],
                T02_DIR / "private" / "tests" / "conftest.py",
                package_name="atavism_pagination",
            )
            first_fail_test = "None"
            first_fail_reason = "None"
            if res.failure_reasons:
                first_key = list(res.failure_reasons.keys())[0]
                first_fail_test = first_key.split("::")[-1]
                first_fail_reason = res.failure_reasons[first_key].splitlines()[0]

            results.append({
                "mutant": name,
                "description": desc,
                "killed": not res.passed,
                "failed_tests_count": res.failed_tests,
                "first_rejecting_test": first_fail_test,
                "rejection_reason": first_fail_reason,
            })
    return results


def audit_t03_mutants() -> list[dict[str, object]]:
    mutants_path = T03_DIR / "private" / "mutants" / "__init__.py"
    code = mutants_path.read_text(encoding="utf-8")

    mutants = [
        ("MutantGlobalKeyService", "Uses raw idempotency key in Treatment (omits tenant scoping)", [T03_DIR / "private" / "tests" / "common", T03_DIR / "private" / "tests" / "treatment"]),
        ("MutantTenantIgnoredService", "Omits tenant ownership check in get_reservation", [T03_DIR / "private" / "tests" / "common"]),
        ("MutantPayloadBlindService", "Returns previous result even when payload changes", [T03_DIR / "private" / "tests" / "common"]),
        ("MutantDuplicateCreationService", "Creates new reservation on every repeated request", [T03_DIR / "private" / "tests" / "common"]),
        ("MutantReplayAllocationService", "Consumes a new identifier on replay", [T03_DIR / "private" / "tests" / "common"]),
        ("MutantConflictMutationService", "Modifies stored state before raising a conflict", [T03_DIR / "private" / "tests" / "common"]),
        ("MutantValidationOrderService", "Checks idempotency before input validation", [T03_DIR / "private" / "tests" / "common"]),
        ("MutantBooleanQuantityService", "Accepts True/False as valid quantity", [T03_DIR / "private" / "tests" / "common"]),
        ("MutantCrossTenantLeakService", "Returns another tenant's reservation during collision in Control", [T03_DIR / "private" / "tests" / "common", T03_DIR / "private" / "tests" / "control"]),
        ("MutantTenantKeyCollisionService", "Incorrectly shares idempotency state across tenants in Treatment", [T03_DIR / "private" / "tests" / "common", T03_DIR / "private" / "tests" / "treatment"]),
    ]

    results = []
    for cls_name, desc, tdirs in mutants:
        with tempfile.TemporaryDirectory(prefix=f"t03_mut_{cls_name}_") as td:
            cand = Path(td) / "service.py"
            cand.write_text(
                f"{code}\nReservationService = {cls_name}\n",
                encoding="utf-8",
            )
            res = grade_candidate(
                candidate_path=cand,
                types_path=T03_DIR / "variants" / "A" / "workspace" / "src" / "atavism_reservation" / "types.py",
                test_dirs=tdirs,
                conftest_path=T03_DIR / "private" / "tests" / "conftest.py",
                package_name="atavism_reservation",
                module_name="service.py",
                timeout=30,
            )

            first_fail_test = ""
            first_fail_reason = ""
            for tname, reason in res.failure_reasons.items():
                first_fail_test = tname.split("::")[-1]
                first_fail_reason = reason.split("\n")[0][:100]
                break

            results.append({
                "mutant": cls_name,
                "description": desc,
                "killed": not res.passed,
                "failed_tests_count": res.failed_tests,
                "first_rejecting_test": first_fail_test,
                "rejection_reason": first_fail_reason,
            })
    return results


def main() -> None:
    print("=" * 80)
    print("T01 MUTATION AUDIT (Retry Semantics)")
    print("=" * 80)
    t01_res = audit_t01_mutants()
    killed_t01 = sum(1 for r in t01_res if r["killed"])
    print(f"Killed mutants: {killed_t01}/{len(t01_res)} | Surviving: {len(t01_res) - killed_t01}\n")
    for r in t01_res:
        status = "[KILLED]" if r["killed"] else "[SURVIVED]"
        print(f"{status} {r['mutant']} ({r['failed_tests_count']} tests failed)")
        print(f"       Primary rejecting test: {r['first_rejecting_test']}")
        print(f"       Rejection reason:       {r['rejection_reason']}")
        print(f"       Behavioral intent:      {r['description']}\n")

    print("=" * 80)
    print("T02 MUTATION AUDIT (Pagination Authority)")
    print("=" * 80)
    t02_res = audit_t02_mutants()
    killed_t02 = sum(1 for r in t02_res if r["killed"])
    print(f"Killed mutants: {killed_t02}/{len(t02_res)} | Surviving: {len(t02_res) - killed_t02}\n")
    for r in t02_res:
        status = "[KILLED]" if r["killed"] else "[SURVIVED]"
        print(f"{status} {r['mutant']} ({r['failed_tests_count']} tests failed)")
        print(f"       Primary rejecting test: {r['first_rejecting_test']}")
        print(f"       Rejection reason:       {r['rejection_reason']}")
        print(f"       Behavioral intent:      {r['description']}\n")

    print("=" * 80)
    print("T03 MUTATION AUDIT (Tenant Isolation and Idempotency Scope)")
    print("=" * 80)
    t03_res = audit_t03_mutants()
    killed_t03 = sum(1 for r in t03_res if r["killed"])
    print(f"Killed mutants: {killed_t03}/{len(t03_res)} | Surviving: {len(t03_res) - killed_t03}\n")
    for r in t03_res:
        status = "[KILLED]" if r["killed"] else "[SURVIVED]"
        print(f"{status} {r['mutant']} ({r['failed_tests_count']} tests failed)")
        print(f"       Primary rejecting test: {r['first_rejecting_test']}")
        print(f"       Rejection reason:       {r['rejection_reason']}")
        print(f"       Behavioral intent:      {r['description']}\n")


if __name__ == "__main__":
    main()

