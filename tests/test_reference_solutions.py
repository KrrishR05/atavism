"""Tests for reference solution correctness using the shared grading interface.

Runs the hidden test suite against both reference implementations
to verify they pass their respective graders and produce correct diagnostics.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from atavism.grading import grade_candidate, grade_task_candidate

TASK_DIR = Path(__file__).resolve().parent.parent / "benchmark" / "tasks" / "T01_retry_semantics"
PRIVATE = TASK_DIR / "private"
TYPES_PATH = TASK_DIR / "variants" / "A" / "workspace" / "src" / "atavism_retry" / "types.py"
CONFTEST_PATH = PRIVATE / "tests" / "conftest.py"


def _grade_t01_subsuite(candidate_path: Path, test_dirs: list[Path]) -> bool:
    res = grade_candidate(
        candidate_path=candidate_path,
        types_path=TYPES_PATH,
        test_dirs=test_dirs,
        conftest_path=CONFTEST_PATH,
        package_name="atavism_retry",
        module_name="client.py",
    )
    return res.passed


class TestReferenceSolutions:
    """Reference implementations must pass their graders via shared infrastructure."""

    def test_control_reference_passes_common_tests(self) -> None:
        passed = _grade_t01_subsuite(
            PRIVATE / "reference" / "control.py",
            [PRIVATE / "tests" / "common"],
        )
        assert passed, "Control reference failed common tests"

    def test_control_reference_passes_control_tests(self) -> None:
        passed = _grade_t01_subsuite(
            PRIVATE / "reference" / "control.py",
            [PRIVATE / "tests" / "control"],
        )
        assert passed, "Control reference failed control tests"

    def test_treatment_reference_passes_common_tests(self) -> None:
        passed = _grade_t01_subsuite(
            PRIVATE / "reference" / "treatment.py",
            [PRIVATE / "tests" / "common"],
        )
        assert passed, "Treatment reference failed common tests"

    def test_treatment_reference_passes_treatment_tests(self) -> None:
        passed = _grade_t01_subsuite(
            PRIVATE / "reference" / "treatment.py",
            [PRIVATE / "tests" / "treatment"],
        )
        assert passed, "Treatment reference failed treatment tests"

    def test_control_reference_fails_treatment_tests(self) -> None:
        """Control reference should FAIL treatment-specific tests
        (because it doesn't retry 409 LEASE_BUSY)."""
        passed = _grade_t01_subsuite(
            PRIVATE / "reference" / "control.py",
            [PRIVATE / "tests" / "treatment"],
        )
        assert not passed, "Control reference should fail treatment tests but passed"

    def test_treatment_reference_fails_control_tests(self) -> None:
        """Treatment reference should FAIL control-specific tests
        (because it retries 409 LEASE_BUSY, which control says not to)."""
        passed = _grade_t01_subsuite(
            PRIVATE / "reference" / "treatment.py",
            [PRIVATE / "tests" / "control"],
        )
        assert not passed, "Treatment reference should fail control tests but passed"

    def test_control_reference_full_task_grading(self) -> None:
        """Verify grade_task_candidate grades Variant A completely."""
        res = grade_task_candidate(TASK_DIR, "A", PRIVATE / "reference" / "control.py")
        assert res.passed is True
        assert res.total_tests == 47
        assert "common_mechanics" in res.diagnostics
        assert res.diagnostics["common_mechanics"].passed_all is True
        assert "pure_convention" in res.diagnostics
        assert res.diagnostics["pure_convention"].passed_all is True
        assert "compound_interactions" in res.diagnostics
        assert res.diagnostics["compound_interactions"].passed_all is True

    def test_treatment_reference_full_task_grading(self) -> None:
        """Verify grade_task_candidate grades Variant B completely."""
        res = grade_task_candidate(TASK_DIR, "B", PRIVATE / "reference" / "treatment.py")
        assert res.passed is True
        assert res.total_tests == 50
        assert "common_mechanics" in res.diagnostics
        assert res.diagnostics["common_mechanics"].passed_all is True
        assert "pure_convention" in res.diagnostics
        assert res.diagnostics["pure_convention"].passed_all is True
        assert "compound_interactions" in res.diagnostics
        assert res.diagnostics["compound_interactions"].passed_all is True

    def test_alt_control_positive_control_passes_variant_a(self) -> None:
        """Verify alternative valid control implementation passes all Variant A tests."""
        res = grade_task_candidate(TASK_DIR, "A", PRIVATE / "reference" / "alt_control.py")
        assert res.passed is True
        assert res.total_tests == 47
        assert res.diagnostics["common_mechanics"].passed_all is True
        assert res.diagnostics["pure_convention"].passed_all is True
        assert res.diagnostics["compound_interactions"].passed_all is True

    def test_alt_treatment_positive_control_passes_variant_b(self) -> None:
        """Verify alternative valid treatment implementation passes all Variant B tests."""
        res = grade_task_candidate(TASK_DIR, "B", PRIVATE / "reference" / "alt_treatment.py")
        assert res.passed is True
        assert res.total_tests == 50
        assert res.diagnostics["common_mechanics"].passed_all is True
        assert res.diagnostics["pure_convention"].passed_all is True
        assert res.diagnostics["compound_interactions"].passed_all is True
