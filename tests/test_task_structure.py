"""Tests for task structure and metadata integrity."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

TASK_DIR = Path(__file__).resolve().parent.parent / "benchmark" / "tasks" / "T01_retry_semantics"


class TestTaskStructure:
    """Validate T01 directory structure and metadata."""

    def test_task_json_exists(self) -> None:
        assert (TASK_DIR / "task.json").is_file()

    def test_task_json_valid(self) -> None:
        with open(TASK_DIR / "task.json") as f:
            data = json.load(f)
        assert data["id"] == "T01"
        assert "A" in data["variants"]
        assert "B" in data["variants"]

    @pytest.mark.parametrize("variant", ["A", "B"])
    def test_workspace_files_exist(self, variant: str) -> None:
        ws = TASK_DIR / "variants" / variant / "workspace"
        assert (ws / "TASK.md").is_file()
        assert (ws / "contract.md").is_file()
        assert (ws / "src" / "atavism_retry" / "__init__.py").is_file()
        assert (ws / "src" / "atavism_retry" / "types.py").is_file()
        assert (ws / "src" / "atavism_retry" / "client.py").is_file()

    def test_reference_solutions_exist(self) -> None:
        private = TASK_DIR / "private"
        assert (private / "reference" / "control.py").is_file()
        assert (private / "reference" / "treatment.py").is_file()

    def test_test_directories_exist(self) -> None:
        tests = TASK_DIR / "private" / "tests"
        assert (tests / "common").is_dir()
        assert (tests / "control").is_dir()
        assert (tests / "treatment").is_dir()
        assert (tests / "conftest.py").is_file()

    def test_mutants_exist(self) -> None:
        assert (TASK_DIR / "private" / "mutants" / "__init__.py").is_file()

    @pytest.mark.parametrize("variant", ["A", "B"])
    def test_types_identical_across_variants(self, variant: str) -> None:
        """Both variants must use the same type definitions."""
        types_a = (TASK_DIR / "variants" / "A" / "workspace" / "src" / "atavism_retry" / "types.py").read_text()
        types_b = (TASK_DIR / "variants" / "B" / "workspace" / "src" / "atavism_retry" / "types.py").read_text()
        assert types_a == types_b

    def test_starter_code_identical(self) -> None:
        """Starter client.py must be identical across variants."""
        client_a = (TASK_DIR / "variants" / "A" / "workspace" / "src" / "atavism_retry" / "client.py").read_text()
        client_b = (TASK_DIR / "variants" / "B" / "workspace" / "src" / "atavism_retry" / "client.py").read_text()
        assert client_a == client_b

    def test_task_md_identical(self) -> None:
        """TASK.md must be identical across variants."""
        task_a = (TASK_DIR / "variants" / "A" / "workspace" / "TASK.md").read_text()
        task_b = (TASK_DIR / "variants" / "B" / "workspace" / "TASK.md").read_text()
        assert task_a == task_b

    def test_contracts_differ(self) -> None:
        """contract.md must differ between variants (the experimental variable)."""
        contract_a = (TASK_DIR / "variants" / "A" / "workspace" / "contract.md").read_text()
        contract_b = (TASK_DIR / "variants" / "B" / "workspace" / "contract.md").read_text()
        assert contract_a != contract_b
        # B should mention LEASE_BUSY as retryable
        assert "LEASE_BUSY" in contract_b

