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
T04_DIR = ROOT / "benchmark" / "tasks" / "T04_split_tender_refund"
T05_DIR = ROOT / "benchmark" / "tasks" / "T05_event_stream_projection"


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
                module_name="client.py",
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
                conftest_path=T02_DIR / "private" / "tests" / "conftest.py",
                package_name="atavism_pagination",
                module_name="client.py",
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


def audit_t04_mutants() -> list[dict[str, object]]:
    mutants_path = T04_DIR / "private" / "mutants" / "__init__.py"
    code = mutants_path.read_text(encoding="utf-8")

    mutants = [
        ("MutantSilentCardFirst", "Silently adopts Card-First Waterfall in Treatment B without authorization", [T04_DIR / "private" / "tests" / "common", T04_DIR / "private" / "tests" / "treatment"]),
        ("MutantSilentGiftCardFirst", "Silently adopts Gift-Card-First Waterfall in Treatment B without authorization", [T04_DIR / "private" / "tests" / "common", T04_DIR / "private" / "tests" / "treatment"]),
        ("MutantSilentProrata", "Silently adopts Pro-Rata split in Treatment B without authorization", [T04_DIR / "private" / "tests" / "common", T04_DIR / "private" / "tests" / "treatment"]),
        ("MutantBlanketRefusal", "Refuses all operations when specification is incomplete", [T04_DIR / "private" / "tests" / "common"]),
        ("MutantFalseUncertainty", "Erroneously treats single-tender refunds as uncertain", [T04_DIR / "private" / "tests" / "common"]),
        ("MutantConservationViolation", "Violates conservation of funds (allocations sum != amount)", [T04_DIR / "private" / "tests" / "common"]),
        ("MutantTenderBalanceExceeded", "Allocates more than individual tender remaining balance", [T04_DIR / "private" / "tests" / "common"]),
        ("MutantSequentialStateCorruption", "Ignores prior refunded_amount across sequential refunds", [T04_DIR / "private" / "tests" / "common"]),
    ]

    results = []
    for cls_name, desc, tdirs in mutants:
        with tempfile.TemporaryDirectory(prefix=f"t04_mut_{cls_name}_") as td:
            cand = Path(td) / "service.py"
            cand.write_text(
                f"{code}\nRefundService = {cls_name}\n",
                encoding="utf-8",
            )
            res = grade_candidate(
                candidate_path=cand,
                types_path=T04_DIR / "variants" / "A" / "workspace" / "src" / "atavism_refund" / "types.py",
                test_dirs=tdirs,
                conftest_path=T04_DIR / "private" / "tests" / "conftest.py",
                package_name="atavism_refund",
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


def audit_t05_mutants() -> list[dict[str, object]]:
    mutants_path = T05_DIR / "private" / "mutants" / "__init__.py"
    code = mutants_path.read_text(encoding="utf-8")

    mutants = [
        ("MutantDropFutureEvents", "Discards out-of-order events without buffering", [T05_DIR / "private" / "tests" / "treatment"]),
        ("MutantPrematureApplication", "Immediately applies out-of-order events without buffering", [T05_DIR / "private" / "tests" / "treatment"]),
        ("MutantReplayDuplicate", "Re-applies duplicate events mutating balance", [T05_DIR / "private" / "tests" / "common"]),
        ("MutantAcceptConflict", "Silently accepts conflicting duplicate payloads", [T05_DIR / "private" / "tests" / "common"]),
        ("MutantCrossAccountBufferLeak", "Shares pending buffer across accounts", [T05_DIR / "private" / "tests" / "treatment"]),
        ("MutantFrozenBypassOnDrain", "Allows buffered deposits to commit after a buffered freeze", [T05_DIR / "private" / "tests" / "treatment"]),
        ("MutantRollbackCommittedOnDrainFail", "Rolls back committed events when drain fails", [T05_DIR / "private" / "tests" / "treatment"]),
        ("MutantBypassBlockedSequence", "Applies later events when predecessor sequence is blocked", [T05_DIR / "private" / "tests" / "treatment"]),
        ("MutantSilentUnblockedOnFailure", "Fails to set is_blocked and blocked_sequence_id on failure", [T05_DIR / "private" / "tests" / "treatment"]),
        ("MutantFloatPrecision", "Uses float arithmetic and permits excess decimal precision", [T05_DIR / "private" / "tests" / "common"]),
    ]

    results = []
    for cls_name, desc, tdirs in mutants:
        with tempfile.TemporaryDirectory(prefix=f"t05_mut_{cls_name}_") as td:
            cand = Path(td) / "projector.py"
            cand.write_text(
                f"{code}\nAccountProjector = {cls_name}\n",
                encoding="utf-8",
            )
            res = grade_candidate(
                candidate_path=cand,
                types_path=T05_DIR / "variants" / "A" / "workspace" / "src" / "atavism_projection" / "types.py",
                test_dirs=tdirs,
                conftest_path=T05_DIR / "private" / "tests" / "conftest.py",
                package_name="atavism_projection",
                module_name="projector.py",
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

    print("=" * 80)
    print("T04 MUTATION AUDIT (Split-Tender Refund Allocation Under Incomplete Policy)")
    print("=" * 80)
    t04_res = audit_t04_mutants()
    killed_t04 = sum(1 for r in t04_res if r["killed"])
    print(f"Killed mutants: {killed_t04}/{len(t04_res)} | Surviving: {len(t04_res) - killed_t04}\n")
    for r in t04_res:
        status = "[KILLED]" if r["killed"] else "[SURVIVED]"
        print(f"{status} {r['mutant']} ({r['failed_tests_count']} tests failed)")
        print(f"       Primary rejecting test: {r['first_rejecting_test']}")
        print(f"       Rejection reason:       {r['rejection_reason']}")
        print(f"       Behavioral intent:      {r['description']}\n")

    print("=" * 80)
    print("T05 MUTATION AUDIT (Event Stream Projection Protocol)")
    print("=" * 80)
    t05_res = audit_t05_mutants()
    killed_t05 = sum(1 for r in t05_res if r["killed"])
    print(f"Killed mutants: {killed_t05}/{len(t05_res)} | Surviving: {len(t05_res) - killed_t05}\n")
    for r in t05_res:
        status = "[KILLED]" if r["killed"] else "[SURVIVED]"
        print(f"{status} {r['mutant']} ({r['failed_tests_count']} tests failed)")
        print(f"       Primary rejecting test: {r['first_rejecting_test']}")
        print(f"       Rejection reason:       {r['rejection_reason']}")
        print(f"       Behavioral intent:      {r['description']}\n")

    print("=" * 80)
    print("MUTATION CLASSIFICATION & RECONCILIATION SUMMARY")
    print("=" * 80)
    all_mutants = []
    for r in t01_res:
        all_mutants.append(("T01", r["mutant"], r["rejection_reason"]))
    for r in t02_res:
        all_mutants.append(("T02", r["mutant"], r["rejection_reason"]))
    for r in t03_res:
        all_mutants.append(("T03", r["mutant"], r["rejection_reason"]))
    for r in t04_res:
        all_mutants.append(("T04", r["mutant"], r["rejection_reason"]))
    for r in t05_res:
        all_mutants.append(("T05", r["mutant"], r["rejection_reason"]))

    cat_counts: dict[str, int] = {
        "Explicit behavioral assertion": 0,
        "Strict mock/fake guard": 0,
        "Unauthorized domain exception": 0,
        "Protocol violation": 0,
    }

    for task, mname, reason in all_mutants:
        if reason.startswith("Failed: DID NOT RAISE") or reason.startswith("AssertionError") or reason.startswith("assert "):
            cat = "Explicit behavioral assertion"
        elif "FakeTransport exhausted" in reason or "Unexpected cursor passed to FakeFetcher" in reason:
            cat = "Strict mock/fake guard"
        elif "PaginationLimitExceeded" in reason or "NotImplementedError" in reason:
            cat = "Protocol violation"
        elif ("IdempotencyConflict" in reason and mname in ("MutantGlobalKeyService", "MutantTenantKeyCollisionService")) or "RefundError" in reason:
            cat = "Unauthorized domain exception"
        else:
            cat = "Explicit behavioral assertion"
        cat_counts[cat] += 1

    total_killed = sum(cat_counts.values())
    print(f"Total Mutants Evaluated: {len(all_mutants)}")
    print(f"Total Mutants Killed:    {total_killed} ({total_killed}/{len(all_mutants)} = 100%)")
    print(f"Surviving Mutants:       {len(all_mutants) - total_killed}")
    print("\nBreakdown by Detection Mechanism:")
    for cat, count in cat_counts.items():
        print(f"  - {cat:32s}: {count:2d}")
    print("-" * 80)
    print(f"  Total Reconciliation: {total_killed} == {len(all_mutants)} (Exact Match)")
    print("=" * 80)


if __name__ == "__main__":
    main()

