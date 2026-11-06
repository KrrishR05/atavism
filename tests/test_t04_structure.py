"""Structural and pairing integrity tests for Task T04 (Split-Tender Refund Allocation)."""

from __future__ import annotations

import difflib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TASK_DIR = ROOT / "benchmark" / "tasks" / "T04_split_tender_refund"


class TestT04TaskStructure:
    """Verify T04 directory layout, metadata schema, and variant pairing."""

    def test_task_json_exists(self) -> None:
        assert (TASK_DIR / "task.json").is_file()

    def test_task_json_valid(self) -> None:
        with open(TASK_DIR / "task.json", encoding="utf-8") as f:
            data = json.load(f)

        assert data["id"] == "T04"
        assert data["dimension"] == "Uncertainty Handling Under Incomplete Specifications"
        assert "A" in data["variants"]
        assert "B" in data["variants"]
        assert "execution" in data
        assert data["execution"]["package_name"] == "atavism_refund"
        assert data["execution"]["module_name"] == "service.py"
        assert data["execution"]["types_file"] == "src/atavism_refund/types.py"

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
        assert (ws / "src" / "atavism_refund" / "__init__.py").is_file()
        assert (ws / "src" / "atavism_refund" / "types.py").is_file()
        assert (ws / "src" / "atavism_refund" / "service.py").is_file()

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
        assert (tests_dir / "common" / "test_single_tender.py").is_file()
        assert (tests_dir / "common" / "test_split_full_refund.py").is_file()
        assert (tests_dir / "common" / "test_integrity.py").is_file()
        assert (tests_dir / "control" / "test_control_policy.py").is_file()
        assert (tests_dir / "treatment" / "test_treatment_policy.py").is_file()
        assert (tests_dir / "treatment" / "test_treatment_isolation.py").is_file()

    def test_mutants_exist(self) -> None:
        assert (TASK_DIR / "private" / "mutants" / "__init__.py").is_file()

    def test_types_identical_across_variants(self) -> None:
        types_a = (TASK_DIR / "variants" / "A" / "workspace" / "src" / "atavism_refund" / "types.py").read_bytes()
        types_b = (TASK_DIR / "variants" / "B" / "workspace" / "src" / "atavism_refund" / "types.py").read_bytes()
        assert types_a == types_b

    def test_task_md_identical_across_variants(self) -> None:
        task_a = (TASK_DIR / "variants" / "A" / "workspace" / "TASK.md").read_bytes()
        task_b = (TASK_DIR / "variants" / "B" / "workspace" / "TASK.md").read_bytes()
        assert task_a == task_b

    def test_starter_code_identical_across_variants(self) -> None:
        starter_a = (TASK_DIR / "variants" / "A" / "workspace" / "src" / "atavism_refund" / "service.py").read_bytes()
        starter_b = (TASK_DIR / "variants" / "B" / "workspace" / "src" / "atavism_refund" / "service.py").read_bytes()
        assert starter_a == starter_b

    def test_contracts_differ_only_in_split_tender_partial_allocation(self) -> None:
        contract_a = (TASK_DIR / "variants" / "A" / "workspace" / "contract.md").read_text(encoding="utf-8").splitlines(keepends=True)
        contract_b = (TASK_DIR / "variants" / "B" / "workspace" / "contract.md").read_text(encoding="utf-8").splitlines(keepends=True)

        diff = list(difflib.unified_diff(contract_a, contract_b, fromfile="A/contract.md", tofile="B/contract.md"))
        diff_text = "".join(diff)

        # Difference must occur only in Section 4.2
        assert "### 4.2 Split-Tender Partial Refund Allocation" in diff_text
        assert "Card-Priority Waterfall Order" in diff_text

