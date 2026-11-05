"""Structural tests for task T02 — Pagination Continuation Under Conflicting Implementation Guidance."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

TASK_DIR = Path(__file__).resolve().parent.parent / "benchmark" / "tasks" / "T02_pagination_authority"


class TestT02TaskStructure:
    """Validate T02 directory layout and metadata integrity."""

    def test_task_json_exists(self) -> None:
        assert (TASK_DIR / "task.json").is_file()

    def test_task_json_valid(self) -> None:
        with open(TASK_DIR / "task.json", encoding="utf-8") as f:
            data = json.load(f)
        assert data["id"] == "T02"
        assert "A" in data["variants"]
        assert "B" in data["variants"]
        assert data["dimension"] == "Specification Conflict Resolution"
        assert "expected_diff_files" in data

    @pytest.mark.parametrize("variant", ["A", "B"])
    def test_workspace_files_exist(self, variant: str) -> None:
        ws = TASK_DIR / "variants" / variant / "workspace"
        assert (ws / "TASK.md").is_file()
        assert (ws / "contract.md").is_file()
        assert (ws / "src" / "atavism_pagination" / "__init__.py").is_file()
        assert (ws / "src" / "atavism_pagination" / "types.py").is_file()
        assert (ws / "src" / "atavism_pagination" / "client.py").is_file()

    def test_reference_solution_exists(self) -> None:
        assert (TASK_DIR / "private" / "reference" / "solution.py").is_file()

    def test_test_files_exist(self) -> None:
        tests = TASK_DIR / "private" / "tests"
        assert (tests / "conftest.py").is_file()
        assert (tests / "test_pagination.py").is_file()

    def test_mutants_exist(self) -> None:
        assert (TASK_DIR / "private" / "mutants" / "__init__.py").is_file()

    def test_types_identical_across_variants(self) -> None:
        types_a = (TASK_DIR / "variants" / "A" / "workspace" / "src" / "atavism_pagination" / "types.py").read_text(encoding="utf-8")
        types_b = (TASK_DIR / "variants" / "B" / "workspace" / "src" / "atavism_pagination" / "types.py").read_text(encoding="utf-8")
        assert types_a == types_b

    def test_contracts_identical_across_variants(self) -> None:
        """In T02, the contract is identical across variants (isolating the comment variable)."""
        contract_a = (TASK_DIR / "variants" / "A" / "workspace" / "contract.md").read_text(encoding="utf-8")
        contract_b = (TASK_DIR / "variants" / "B" / "workspace" / "contract.md").read_text(encoding="utf-8")
        assert contract_a == contract_b

    def test_task_md_identical_across_variants(self) -> None:
        """In T02, task instructions are identical across variants."""
        task_a = (TASK_DIR / "variants" / "A" / "workspace" / "TASK.md").read_text(encoding="utf-8")
        task_b = (TASK_DIR / "variants" / "B" / "workspace" / "TASK.md").read_text(encoding="utf-8")
        assert task_a == task_b

    def test_client_stubs_differ_only_in_comment(self) -> None:
        """Starter client.py must differ only in the designated comment block."""
        client_a = (TASK_DIR / "variants" / "A" / "workspace" / "src" / "atavism_pagination" / "client.py").read_text(encoding="utf-8")
        client_b = (TASK_DIR / "variants" / "B" / "workspace" / "src" / "atavism_pagination" / "client.py").read_text(encoding="utf-8")
        assert client_a != client_b
        assert "Pagination continuation is controlled by has_more." in client_a
        assert "Pagination continuation is controlled by next_cursor." in client_b
        assert "Legacy" not in client_b

