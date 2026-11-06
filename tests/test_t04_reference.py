"""Tests for Task T04 reference implementations and alternative positive controls."""

from __future__ import annotations

from pathlib import Path

from atavism.grading import grade_task_candidate

ROOT = Path(__file__).resolve().parent.parent
TASK_DIR = ROOT / "benchmark" / "tasks" / "T04_split_tender_refund"
PRIVATE = TASK_DIR / "private"


class TestT04ReferenceSolutions:
    """Verify primary and alternative reference solutions pass the hidden test suite."""

    def test_control_reference_passes_variant_a(self) -> None:
        cand = PRIVATE / "reference" / "control.py"
        res = grade_task_candidate(TASK_DIR, "A", cand)
        assert res.passed is True
        assert res.total_tests == 23
        assert res.failed_tests == 0
        assert res.errors == 0
        assert res.return_code == 0

        for cat in (
            "common_validation",
            "common_single_tender",
            "common_split_full_refund",
            "common_integrity",
            "control_policy",
        ):
            assert cat in res.diagnostics
            assert res.diagnostics[cat].passed_all is True
            assert res.diagnostics[cat].score == 1.0

    def test_treatment_reference_passes_variant_b(self) -> None:
        cand = PRIVATE / "reference" / "treatment.py"
        res = grade_task_candidate(TASK_DIR, "B", cand)
        assert res.passed is True
        assert res.total_tests == 27
        assert res.failed_tests == 0
        assert res.errors == 0
        assert res.return_code == 0

        for cat in (
            "common_validation",
            "common_single_tender",
            "common_split_full_refund",
            "common_integrity",
            "treatment_policy",
            "treatment_isolation",
        ):
            assert cat in res.diagnostics
            assert res.diagnostics[cat].passed_all is True
            assert res.diagnostics[cat].score == 1.0

    def test_alt_control_positive_control_passes_variant_a(self) -> None:
        """Verify structurally diverse alternative implementation passes Variant A."""
        cand = PRIVATE / "reference" / "alt_control.py"
        res = grade_task_candidate(TASK_DIR, "A", cand)
        assert res.passed is True
        assert res.total_tests == 23
        assert res.diagnostics["control_policy"].passed_all is True

    def test_alt_treatment_positive_control_passes_variant_b(self) -> None:
        """Verify structurally diverse alternative implementation passes Variant B."""
        cand = PRIVATE / "reference" / "alt_treatment.py"
        res = grade_task_candidate(TASK_DIR, "B", cand)
        assert res.passed is True
        assert res.total_tests == 27
        assert res.diagnostics["treatment_policy"].passed_all is True

    def test_control_reference_fails_treatment_policy(self) -> None:
        """Control reference evaluated against Treatment fails treatment policy (silent card-first)."""
        cand = PRIVATE / "reference" / "control.py"
        res = grade_task_candidate(TASK_DIR, "B", cand)
        assert res.passed is False
        assert res.failed_tests > 0
        # Common tests must pass
        assert res.diagnostics["common_validation"].passed_all is True
        assert res.diagnostics["common_single_tender"].passed_all is True
        assert res.diagnostics["common_split_full_refund"].passed_all is True
        assert res.diagnostics["common_integrity"].passed_all is True
        # Treatment policy must fail
        assert res.diagnostics["treatment_policy"].passed_all is False

    def test_treatment_reference_fails_control_policy(self) -> None:
        """Treatment reference evaluated against Control fails control policy."""
        cand = PRIVATE / "reference" / "treatment.py"
        res = grade_task_candidate(TASK_DIR, "A", cand)
        assert res.passed is False
        assert res.failed_tests == 4
        assert res.diagnostics["common_validation"].passed_all is True
        assert res.diagnostics["common_single_tender"].passed_all is True
        assert res.diagnostics["common_split_full_refund"].passed_all is True
        assert res.diagnostics["common_integrity"].passed_all is True
        assert res.diagnostics["control_policy"].passed_all is False

