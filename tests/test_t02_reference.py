"""Tests for T02 reference solution correctness using the shared grading interface.

Runs the hidden test suite against the reference solution to verify
it passes all contract requirements.
"""

from __future__ import annotations

from pathlib import Path

from atavism.grading import grade_task_candidate

TASK_DIR = Path(__file__).resolve().parent.parent / "benchmark" / "tasks" / "T02_pagination_authority"
PRIVATE = TASK_DIR / "private"


class TestT02ReferenceSolution:
    """The reference implementation must pass the entire test suite via shared grader."""

    def test_reference_solution_passes(self) -> None:
        ref_path = PRIVATE / "reference" / "solution.py"
        res = grade_task_candidate(TASK_DIR, "A", ref_path)
        assert res.passed is True, f"Reference solution failed test suite:\n{res.output}"
        assert res.total_tests == 29
        assert "contract_compliance" in res.diagnostics
        assert res.diagnostics["contract_compliance"].passed_all is True

    def test_alt_solution_positive_control_passes(self) -> None:
        """Verify alternative generator-based implementation passes all tests."""
        ref_path = PRIVATE / "reference" / "alt_solution.py"
        res = grade_task_candidate(TASK_DIR, "A", ref_path)
        assert res.passed is True, f"Alternative solution failed test suite:\n{res.output}"
        assert res.total_tests == 29
        assert "contract_compliance" in res.diagnostics
        assert res.diagnostics["contract_compliance"].passed_all is True
