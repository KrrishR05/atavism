"""Tests for Task T04 grader and mutation fixture verification."""

from __future__ import annotations

import tempfile
from pathlib import Path

from atavism.grading import grade_candidate

ROOT = Path(__file__).resolve().parent.parent
TASK_DIR = ROOT / "benchmark" / "tasks" / "T04_split_tender_refund"
PRIVATE = TASK_DIR / "private"
TYPES_PATH = TASK_DIR / "variants" / "A" / "workspace" / "src" / "atavism_refund" / "types.py"
CONFTEST_PATH = PRIVATE / "tests" / "conftest.py"
COMMON_TESTS = PRIVATE / "tests" / "common"
CONTROL_TESTS = PRIVATE / "tests" / "control"
TREATMENT_TESTS = PRIVATE / "tests" / "treatment"


def _grade_mutant(mutant_class_name: str, test_dirs: list[Path]) -> tuple[bool, int, str]:
    mutants_code = (PRIVATE / "mutants" / "__init__.py").read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="t04_mutant_test_") as tmpdir:
        cand_path = Path(tmpdir) / "service.py"
        cand_path.write_text(
            f"{mutants_code}\nRefundService = {mutant_class_name}\n",
            encoding="utf-8",
        )
        res = grade_candidate(
            candidate_path=cand_path,
            types_path=TYPES_PATH,
            test_dirs=test_dirs,
            conftest_path=CONFTEST_PATH,
            package_name="atavism_refund",
            module_name="service.py",
            timeout=30,
        )
        return res.passed, res.failed_tests, res.output


class TestT04MutantsRejected:
    """Verify that all 8 mutation fixtures are rejected by the hidden test suite."""

    def test_mutant_silent_card_first_rejected_in_treatment(self) -> None:
        passed, failed, _ = _grade_mutant("MutantSilentCardFirst", [COMMON_TESTS, TREATMENT_TESTS])
        assert passed is False
        assert failed > 0

    def test_mutant_silent_gift_card_first_rejected_in_treatment(self) -> None:
        passed, failed, _ = _grade_mutant("MutantSilentGiftCardFirst", [COMMON_TESTS, TREATMENT_TESTS])
        assert passed is False
        assert failed > 0

    def test_mutant_silent_prorata_rejected_in_treatment(self) -> None:
        passed, failed, _ = _grade_mutant("MutantSilentProrata", [COMMON_TESTS, TREATMENT_TESTS])
        assert passed is False
        assert failed > 0

    def test_mutant_blanket_refusal_rejected(self) -> None:
        passed, failed, _ = _grade_mutant("MutantBlanketRefusal", [COMMON_TESTS])
        assert passed is False
        assert failed > 0

    def test_mutant_false_uncertainty_rejected(self) -> None:
        passed, failed, _ = _grade_mutant("MutantFalseUncertainty", [COMMON_TESTS])
        assert passed is False
        assert failed > 0

    def test_mutant_conservation_violation_rejected(self) -> None:
        passed, failed, _ = _grade_mutant("MutantConservationViolation", [COMMON_TESTS])
        assert passed is False
        assert failed > 0

    def test_mutant_tender_balance_exceeded_rejected(self) -> None:
        passed, failed, _ = _grade_mutant("MutantTenderBalanceExceeded", [COMMON_TESTS])
        assert passed is False
        assert failed > 0

    def test_mutant_sequential_state_corruption_rejected(self) -> None:
        passed, failed, _ = _grade_mutant("MutantSequentialStateCorruption", [COMMON_TESTS])
        assert passed is False
        assert failed > 0

