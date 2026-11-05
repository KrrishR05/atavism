"""Tests for Task T03 reference implementations and alternative positive controls."""

from __future__ import annotations

from pathlib import Path

from atavism.grading import grade_task_candidate

ROOT = Path(__file__).resolve().parent.parent
TASK_DIR = ROOT / "benchmark" / "tasks" / "T03_tenant_idempotency"
PRIVATE = TASK_DIR / "private"


class TestT03ReferenceSolutions:
    """Verify primary and alternative reference solutions pass the hidden test suite."""

    def test_control_reference_passes_variant_a(self) -> None:
        cand = PRIVATE / "reference" / "control.py"
        res = grade_task_candidate(TASK_DIR, "A", cand)
        assert res.passed is True
        assert res.total_tests == 61
        assert res.failed_tests == 0
        assert res.errors == 0
        assert res.return_code == 0

        for cat in (
            "common_validation_mechanics",
            "same_tenant_idempotency",
            "tenant_isolation",
            "state_integrity",
            "cross_tenant_key_scope",
        ):
            assert cat in res.diagnostics
            assert res.diagnostics[cat].passed_all is True
            assert res.diagnostics[cat].score == 1.0

    def test_treatment_reference_passes_variant_b(self) -> None:
        cand = PRIVATE / "reference" / "treatment.py"
        res = grade_task_candidate(TASK_DIR, "B", cand)
        assert res.passed is True
        assert res.total_tests == 62
        assert res.failed_tests == 0
        assert res.errors == 0
        assert res.return_code == 0

        for cat in (
            "common_validation_mechanics",
            "same_tenant_idempotency",
            "tenant_isolation",
            "state_integrity",
            "cross_tenant_key_scope",
        ):
            assert cat in res.diagnostics
            assert res.diagnostics[cat].passed_all is True
            assert res.diagnostics[cat].score == 1.0

    def test_alt_control_positive_control_passes_variant_a(self) -> None:
        """Verify structurally diverse alternative implementation passes Variant A."""
        cand = PRIVATE / "reference" / "alt_control.py"
        res = grade_task_candidate(TASK_DIR, "A", cand)
        assert res.passed is True
        assert res.total_tests == 61
        assert res.diagnostics["cross_tenant_key_scope"].passed_all is True

    def test_alt_treatment_positive_control_passes_variant_b(self) -> None:
        """Verify structurally diverse alternative implementation passes Variant B."""
        cand = PRIVATE / "reference" / "alt_treatment.py"
        res = grade_task_candidate(TASK_DIR, "B", cand)
        assert res.passed is True
        assert res.total_tests == 62
        assert res.diagnostics["cross_tenant_key_scope"].passed_all is True

    def test_control_reference_fails_treatment_cross_tenant_scope(self) -> None:
        """Control reference evaluated against Treatment fails cross-tenant key scope."""
        cand = PRIVATE / "reference" / "control.py"
        res = grade_task_candidate(TASK_DIR, "B", cand)
        assert res.passed is False
        assert res.failed_tests == 5
        # Common mechanics must pass
        assert res.diagnostics["common_validation_mechanics"].passed_all is True
        assert res.diagnostics["same_tenant_idempotency"].passed_all is True
        assert res.diagnostics["tenant_isolation"].passed_all is True
        assert res.diagnostics["state_integrity"].passed_all is True
        # Cross-tenant scope must fail
        assert res.diagnostics["cross_tenant_key_scope"].passed_all is False
        assert res.diagnostics["cross_tenant_key_scope"].failed == 5

    def test_treatment_reference_fails_control_cross_tenant_scope(self) -> None:
        """Treatment reference evaluated against Control fails cross-tenant key scope."""
        cand = PRIVATE / "reference" / "treatment.py"
        res = grade_task_candidate(TASK_DIR, "A", cand)
        assert res.passed is False
        assert res.failed_tests == 5
        assert res.diagnostics["common_validation_mechanics"].passed_all is True
        assert res.diagnostics["same_tenant_idempotency"].passed_all is True
        assert res.diagnostics["tenant_isolation"].passed_all is True
        assert res.diagnostics["state_integrity"].passed_all is True
        assert res.diagnostics["cross_tenant_key_scope"].passed_all is False
        assert res.diagnostics["cross_tenant_key_scope"].failed == 5

