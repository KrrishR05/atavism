"""Integration tests for shared grading infrastructure across tasks and variants."""

from __future__ import annotations

from pathlib import Path

import pytest

from atavism.grading import GradeResult, grade_task_candidate

ROOT = Path(__file__).resolve().parent.parent
T01_DIR = ROOT / "benchmark" / "tasks" / "T01_retry_semantics"
T02_DIR = ROOT / "benchmark" / "tasks" / "T02_pagination_authority"


class TestSharedGradingInterface:
    """Verify that both tasks and variants grade cleanly through the shared grading API."""

    def test_grade_t01_control_reference(self) -> None:
        cand = T01_DIR / "private" / "reference" / "control.py"
        res = grade_task_candidate(T01_DIR, "A", cand)
        assert isinstance(res, GradeResult)
        assert res.passed is True
        assert res.return_code == 0
        assert res.total_tests == 47
        assert res.failed_tests == 0
        assert res.errors == 0
        assert "common_mechanics" in res.diagnostics
        assert res.diagnostics["common_mechanics"].passed_all is True
        assert "pure_convention" in res.diagnostics
        assert res.diagnostics["pure_convention"].passed_all is True
        assert "compound_interactions" in res.diagnostics
        assert res.diagnostics["compound_interactions"].passed_all is True

    def test_grade_t01_treatment_reference(self) -> None:
        cand = T01_DIR / "private" / "reference" / "treatment.py"
        res = grade_task_candidate(T01_DIR, "B", cand)
        assert isinstance(res, GradeResult)
        assert res.passed is True
        assert res.return_code == 0
        assert res.total_tests == 50
        assert res.failed_tests == 0
        assert "common_mechanics" in res.diagnostics
        assert res.diagnostics["common_mechanics"].passed_all is True
        assert "pure_convention" in res.diagnostics
        assert res.diagnostics["pure_convention"].passed_all is True
        assert "compound_interactions" in res.diagnostics
        assert res.diagnostics["compound_interactions"].passed_all is True

    def test_grade_t02_reference_variant_a(self) -> None:
        cand = T02_DIR / "private" / "reference" / "solution.py"
        res = grade_task_candidate(T02_DIR, "A", cand)
        assert isinstance(res, GradeResult)
        assert res.passed is True
        assert res.total_tests == 29
        assert res.failed_tests == 0
        assert "contract_compliance" in res.diagnostics
        assert res.diagnostics["contract_compliance"].passed_all is True

    def test_grade_t02_reference_variant_b(self) -> None:
        cand = T02_DIR / "private" / "reference" / "solution.py"
        res = grade_task_candidate(T02_DIR, "B", cand)
        assert isinstance(res, GradeResult)
        assert res.passed is True
        assert res.total_tests == 29
        assert res.failed_tests == 0
        assert "contract_compliance" in res.diagnostics
        assert res.diagnostics["contract_compliance"].passed_all is True

    def test_grade_t01_control_candidate_in_treatment_variant(self) -> None:
        """Control candidate fails Variant B because 409 LEASE_BUSY is not retried.

        Diagnostic breakdown must show common_mechanics passed while pure_convention and compound_interactions failed!
        """
        cand = T01_DIR / "private" / "reference" / "control.py"
        res = grade_task_candidate(T01_DIR, "B", cand)
        assert res.passed is False
        assert res.failed_tests > 0
        assert res.diagnostics["common_mechanics"].passed_all is True
        assert res.diagnostics["pure_convention"].passed_all is False
        assert res.diagnostics["pure_convention"].failed == 1
        assert res.diagnostics["pure_convention"].score == 0.0
        assert res.diagnostics["compound_interactions"].passed_all is False
        assert res.diagnostics["compound_interactions"].failed >= 4
