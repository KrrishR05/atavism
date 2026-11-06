"""Tests for Task T05 grader and mutation fixture verification."""

from __future__ import annotations

import tempfile
from pathlib import Path

from atavism.grading import grade_candidate

ROOT = Path(__file__).resolve().parent.parent
TASK_DIR = ROOT / "benchmark" / "tasks" / "T05_event_stream_projection"
PRIVATE = TASK_DIR / "private"
TYPES_PATH = TASK_DIR / "variants" / "A" / "workspace" / "src" / "atavism_projection" / "types.py"
CONFTEST_PATH = PRIVATE / "tests" / "conftest.py"
COMMON_TESTS = PRIVATE / "tests" / "common"
CONTROL_TESTS = PRIVATE / "tests" / "control"
TREATMENT_TESTS = PRIVATE / "tests" / "treatment"


def _grade_mutant(mutant_class_name: str, test_dirs: list[Path]) -> tuple[bool, int, str]:
    mutants_code = (PRIVATE / "mutants" / "__init__.py").read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="t05_mutant_test_") as tmpdir:
        cand_path = Path(tmpdir) / "projector.py"
        cand_path.write_text(
            f"{mutants_code}\nAccountProjector = {mutant_class_name}\n",
            encoding="utf-8",
        )
        res = grade_candidate(
            candidate_path=cand_path,
            types_path=TYPES_PATH,
            test_dirs=test_dirs,
            conftest_path=CONFTEST_PATH,
            package_name="atavism_projection",
            module_name="projector.py",
            timeout=30,
        )
        return res.passed, res.failed_tests, res.output


class TestT05MutantsRejected:
    """Verify that all 10 mutation fixtures are rejected by the hidden test suite."""

    def test_mutant_drop_future_events_rejected(self) -> None:
        passed, failed, _ = _grade_mutant("MutantDropFutureEvents", [COMMON_TESTS, TREATMENT_TESTS])
        assert passed is False
        assert failed > 0

    def test_mutant_premature_application_rejected(self) -> None:
        passed, failed, _ = _grade_mutant("MutantPrematureApplication", [COMMON_TESTS, TREATMENT_TESTS])
        assert passed is False
        assert failed > 0

    def test_mutant_replay_duplicate_rejected(self) -> None:
        passed, failed, _ = _grade_mutant("MutantReplayDuplicate", [COMMON_TESTS])
        assert passed is False
        assert failed > 0

    def test_mutant_accept_conflict_rejected(self) -> None:
        passed, failed, _ = _grade_mutant("MutantAcceptConflict", [COMMON_TESTS])
        assert passed is False
        assert failed > 0

    def test_mutant_cross_account_buffer_leak_rejected(self) -> None:
        passed, failed, _ = _grade_mutant("MutantCrossAccountBufferLeak", [COMMON_TESTS, TREATMENT_TESTS])
        assert passed is False
        assert failed > 0

    def test_mutant_frozen_bypass_on_drain_rejected(self) -> None:
        passed, failed, _ = _grade_mutant("MutantFrozenBypassOnDrain", [COMMON_TESTS, TREATMENT_TESTS])
        assert passed is False
        assert failed > 0

    def test_mutant_rollback_committed_on_drain_fail_rejected(self) -> None:
        passed, failed, _ = _grade_mutant("MutantRollbackCommittedOnDrainFail", [COMMON_TESTS, TREATMENT_TESTS])
        assert passed is False
        assert failed > 0

    def test_mutant_bypass_blocked_sequence_rejected(self) -> None:
        passed, failed, _ = _grade_mutant("MutantBypassBlockedSequence", [COMMON_TESTS, TREATMENT_TESTS])
        assert passed is False
        assert failed > 0

    def test_mutant_silent_unblocked_on_failure_rejected(self) -> None:
        passed, failed, _ = _grade_mutant("MutantSilentUnblockedOnFailure", [COMMON_TESTS, TREATMENT_TESTS])
        assert passed is False
        assert failed > 0

    def test_mutant_float_precision_rejected(self) -> None:
        passed, failed, _ = _grade_mutant("MutantFloatPrecision", [COMMON_TESTS])
        assert passed is False
        assert failed > 0

