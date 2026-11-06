"""Tests for Task T05 reference implementations and alternative positive controls."""

from __future__ import annotations

from pathlib import Path

from atavism.grading import grade_task_candidate

ROOT = Path(__file__).resolve().parent.parent
TASK_DIR = ROOT / "benchmark" / "tasks" / "T05_event_stream_projection"
PRIVATE = TASK_DIR / "private"


class TestT05ReferenceSolutions:
    """Verify primary and alternative reference solutions pass the hidden test suite."""

    def test_control_reference_passes_variant_a(self) -> None:
        cand = PRIVATE / "reference" / "control.py"
        res = grade_task_candidate(TASK_DIR, "A", cand)
        assert res.passed is True
        assert res.total_tests == 84
        assert res.failed_tests == 0
        assert res.errors == 0
        assert res.return_code == 0

        for cat in (
            "common_initialization",
            "common_validation",
            "common_precision",
            "common_identity_and_duplicates",
            "common_domain_transitions",
            "common_frozen_invariants",
            "common_account_isolation",
            "control_fifo_ordering",
        ):
            assert cat in res.diagnostics
            assert res.diagnostics[cat].passed_all is True
            assert res.diagnostics[cat].score == 1.0

    def test_treatment_reference_passes_variant_b(self) -> None:
        cand = PRIVATE / "reference" / "treatment.py"
        res = grade_task_candidate(TASK_DIR, "B", cand)
        assert res.passed is True
        assert res.total_tests == 87
        assert res.failed_tests == 0
        assert res.errors == 0
        assert res.return_code == 0

        for cat in (
            "common_initialization",
            "common_validation",
            "common_precision",
            "common_identity_and_duplicates",
            "common_domain_transitions",
            "common_frozen_invariants",
            "common_account_isolation",
            "treatment_buffering_and_draining",
            "treatment_blocked_stream_semantics",
        ):
            assert cat in res.diagnostics
            assert res.diagnostics[cat].passed_all is True
            assert res.diagnostics[cat].score == 1.0

    def test_alt_control_positive_control_passes_variant_a(self) -> None:
        """Verify structurally diverse alternative implementation passes Variant A."""
        cand = PRIVATE / "reference" / "alt_control.py"
        res = grade_task_candidate(TASK_DIR, "A", cand)
        assert res.passed is True
        assert res.total_tests == 84
        assert res.diagnostics["control_fifo_ordering"].passed_all is True

    def test_alt_treatment_positive_control_passes_variant_b(self) -> None:
        """Verify structurally diverse alternative implementation passes Variant B."""
        cand = PRIVATE / "reference" / "alt_treatment.py"
        res = grade_task_candidate(TASK_DIR, "B", cand)
        assert res.passed is True
        assert res.total_tests == 87
        assert res.diagnostics["treatment_buffering_and_draining"].passed_all is True
        assert res.diagnostics["treatment_blocked_stream_semantics"].passed_all is True

    def test_control_reference_fails_treatment_policy(self) -> None:
        """Control reference evaluated against Treatment fails treatment buffering tests."""
        cand = PRIVATE / "reference" / "control.py"
        res = grade_task_candidate(TASK_DIR, "B", cand)
        assert res.passed is False
        assert res.failed_tests > 0
        # Common tests must pass
        assert res.diagnostics["common_domain_transitions"].passed_all is True

    def test_treatment_reference_fails_control_fifo_policy(self) -> None:
        """Treatment reference evaluated against Control fails FIFO gap tests."""
        cand = PRIVATE / "reference" / "treatment.py"
        res = grade_task_candidate(TASK_DIR, "A", cand)
        assert res.passed is False
        assert res.failed_tests > 0
        # Common tests must pass
        assert res.diagnostics["common_domain_transitions"].passed_all is True
