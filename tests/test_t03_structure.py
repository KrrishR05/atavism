"""Structural and pairing integrity tests for Task T03 (Tenant Isolation and Idempotency Scope)."""

from __future__ import annotations

import difflib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TASK_DIR = ROOT / "benchmark" / "tasks" / "T03_tenant_idempotency"


class TestT03TaskStructure:
    """Verify T03 directory layout, metadata schema, and variant pairing."""

    def test_task_json_exists(self) -> None:
        assert (TASK_DIR / "task.json").is_file()

    def test_task_json_valid(self) -> None:
        with open(TASK_DIR / "task.json", encoding="utf-8") as f:
            data = json.load(f)

        assert data["id"] == "T03"
        assert data["dimension"] == "Semantic Composition Under Interacting Contracts"
        assert "A" in data["variants"]
        assert "B" in data["variants"]
        assert "execution" in data
        assert data["execution"]["package_name"] == "atavism_reservation"
        assert data["execution"]["module_name"] == "service.py"
        assert data["execution"]["types_file"] == "src/atavism_reservation/types.py"

        for v in ("A", "B"):
            assert v in data["execution"]["variants"]
            v_cfg = data["execution"]["variants"][v]
            assert "test_paths" in v_cfg
            assert len(v_cfg["test_paths"]) > 0
            assert "diagnostic_categories" in v_cfg

    @pytest.mark.parametrize("variant", ["A", "B"])
    def test_workspace_files_exist(self, variant: str) -> None:
        ws = TASK_DIR / "variants" / variant / "workspace"
        assert (ws / "TASK.md").is_file()
        assert (ws / "contract.md").is_file()
        assert (ws / "src" / "atavism_reservation" / "__init__.py").is_file()
        assert (ws / "src" / "atavism_reservation" / "types.py").is_file()
        assert (ws / "src" / "atavism_reservation" / "service.py").is_file()

    def test_reference_solutions_exist(self) -> None:
        ref_dir = TASK_DIR / "private" / "reference"
        assert (ref_dir / "control.py").is_file()
        assert (ref_dir / "treatment.py").is_file()
        assert (ref_dir / "alt_control.py").is_file()
        assert (ref_dir / "alt_treatment.py").is_file()

    def test_test_files_exist(self) -> None:
        tests_dir = TASK_DIR / "private" / "tests"
        assert (tests_dir / "conftest.py").is_file()
        assert (tests_dir / "common" / "test_validation.py").is_file()
        assert (tests_dir / "common" / "test_idempotency.py").is_file()
        assert (tests_dir / "common" / "test_isolation.py").is_file()
        assert (tests_dir / "common" / "test_integrity.py").is_file()
        assert (tests_dir / "control" / "test_control_scope.py").is_file()
        assert (tests_dir / "treatment" / "test_treatment_scope.py").is_file()

    def test_mutants_exist(self) -> None:
        assert (TASK_DIR / "private" / "mutants" / "__init__.py").is_file()

    def test_types_identical_across_variants(self) -> None:
        types_a = (TASK_DIR / "variants" / "A" / "workspace" / "src" / "atavism_reservation" / "types.py").read_text(encoding="utf-8")
        types_b = (TASK_DIR / "variants" / "B" / "workspace" / "src" / "atavism_reservation" / "types.py").read_text(encoding="utf-8")
        assert types_a == types_b

    def test_task_md_identical_across_variants(self) -> None:
        task_a = (TASK_DIR / "variants" / "A" / "workspace" / "TASK.md").read_text(encoding="utf-8")
        task_b = (TASK_DIR / "variants" / "B" / "workspace" / "TASK.md").read_text(encoding="utf-8")
        assert task_a == task_b

    def test_starter_code_identical_across_variants(self) -> None:
        stub_a = (TASK_DIR / "variants" / "A" / "workspace" / "src" / "atavism_reservation" / "service.py").read_text(encoding="utf-8")
        stub_b = (TASK_DIR / "variants" / "B" / "workspace" / "src" / "atavism_reservation" / "service.py").read_text(encoding="utf-8")
        assert stub_a == stub_b

    def test_contracts_differ_only_in_idempotency_scope(self) -> None:
        contract_a = (TASK_DIR / "variants" / "A" / "workspace" / "contract.md").read_text(encoding="utf-8").splitlines()
        contract_b = (TASK_DIR / "variants" / "B" / "workspace" / "contract.md").read_text(encoding="utf-8").splitlines()

        diff = list(difflib.unified_diff(contract_a, contract_b, fromfile="A/contract.md", tofile="B/contract.md"))
        diff_text = "\n".join(diff)

        assert "Idempotency Key Scope" in diff_text
        assert "global across the entire service" in diff_text
        assert "scoped per tenant" in diff_text

