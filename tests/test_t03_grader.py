"""Tests for Task T03 grader and mutation fixture verification."""

from __future__ import annotations

import tempfile
from pathlib import Path

from atavism.grading import grade_candidate

ROOT = Path(__file__).resolve().parent.parent
TASK_DIR = ROOT / "benchmark" / "tasks" / "T03_tenant_idempotency"
PRIVATE = TASK_DIR / "private"
TYPES_PATH = TASK_DIR / "variants" / "A" / "workspace" / "src" / "atavism_reservation" / "types.py"
CONFTEST_PATH = PRIVATE / "tests" / "conftest.py"
COMMON_TESTS = PRIVATE / "tests" / "common"
CONTROL_TESTS = PRIVATE / "tests" / "control"
TREATMENT_TESTS = PRIVATE / "tests" / "treatment"


def _grade_mutant(mutant_class_name: str, test_dirs: list[Path]) -> tuple[bool, int, str]:
    mutants_code = (PRIVATE / "mutants" / "__init__.py").read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="t03_mutant_test_") as tmpdir:
        cand_path = Path(tmpdir) / "service.py"
        cand_path.write_text(
            f"{mutants_code}\nReservationService = {mutant_class_name}\n",
            encoding="utf-8",
        )
        res = grade_candidate(
            candidate_path=cand_path,
            types_path=TYPES_PATH,
            test_dirs=test_dirs,
            conftest_path=CONFTEST_PATH,
            package_name="atavism_reservation",
            module_name="service.py",
            timeout=30,
        )
        return res.passed, res.failed_tests, res.output


class TestT03MutantsRejected:
    """Verify that all 10 mutation fixtures are rejected by the hidden test suite."""

    def test_mutant_global_key_rejected_in_treatment(self) -> None:
        passed, failed, output = _grade_mutant("MutantGlobalKeyService", [COMMON_TESTS, TREATMENT_TESTS])
        assert passed is False
        assert failed > 0

    def test_mutant_tenant_ignored_rejected(self) -> None:
        passed, failed, output = _grade_mutant("MutantTenantIgnoredService", [COMMON_TESTS])
        assert passed is False
        assert failed > 0

    def test_mutant_payload_blind_rejected(self) -> None:
        passed, failed, output = _grade_mutant("MutantPayloadBlindService", [COMMON_TESTS])
        assert passed is False
        assert failed > 0

    def test_mutant_duplicate_creation_rejected(self) -> None:
        passed, failed, output = _grade_mutant("MutantDuplicateCreationService", [COMMON_TESTS])
        assert passed is False
        assert failed > 0

    def test_mutant_replay_allocation_rejected(self) -> None:
        passed, failed, output = _grade_mutant("MutantReplayAllocationService", [COMMON_TESTS])
        assert passed is False
        assert failed > 0

    def test_mutant_conflict_mutation_rejected(self) -> None:
        passed, failed, output = _grade_mutant("MutantConflictMutationService", [COMMON_TESTS])
        assert passed is False
        assert failed > 0

    def test_mutant_validation_order_rejected(self) -> None:
        passed, failed, output = _grade_mutant("MutantValidationOrderService", [COMMON_TESTS])
        assert passed is False
        assert failed > 0

    def test_mutant_boolean_quantity_rejected(self) -> None:
        passed, failed, output = _grade_mutant("MutantBooleanQuantityService", [COMMON_TESTS])
        assert passed is False
        assert failed > 0

    def test_mutant_cross_tenant_leak_rejected_in_control(self) -> None:
        passed, failed, output = _grade_mutant("MutantCrossTenantLeakService", [COMMON_TESTS, CONTROL_TESTS])
        assert passed is False
        assert failed > 0

    def test_mutant_tenant_key_collision_rejected_in_treatment(self) -> None:
        passed, failed, output = _grade_mutant("MutantTenantKeyCollisionService", [COMMON_TESTS, TREATMENT_TESTS])
        assert passed is False
        assert failed > 0

