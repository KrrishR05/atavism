"""Tests for T02 workspace isolation — ensuring private evaluation files cannot be exported."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from atavism.workspace import export_workspace, matches_allowlist, validate_workspace

TASK_DIR = Path(__file__).resolve().parent.parent / "benchmark" / "tasks" / "T02_pagination_authority"


class TestT02AllowlistMatching:
    """Test file allowlist pattern matching for T02."""

    def test_task_md_allowed(self) -> None:
        assert matches_allowlist("TASK.md")

    def test_contract_md_allowed(self) -> None:
        assert matches_allowlist("contract.md")

    def test_python_source_allowed(self) -> None:
        assert matches_allowlist("src/atavism_pagination/client.py")
        assert matches_allowlist("src/atavism_pagination/types.py")
        assert matches_allowlist("src/atavism_pagination/__init__.py")

    def test_reference_not_allowed(self) -> None:
        assert not matches_allowlist("private/reference/solution.py")

    def test_test_file_not_allowed(self) -> None:
        assert not matches_allowlist("private/tests/test_pagination.py")

    def test_conftest_not_allowed(self) -> None:
        assert not matches_allowlist("private/tests/conftest.py")

    def test_mutant_not_allowed(self) -> None:
        assert not matches_allowlist("private/mutants/__init__.py")

    def test_task_json_not_allowed(self) -> None:
        assert not matches_allowlist("task.json")


class TestT02WorkspaceValidation:
    """Validate that T02 workspaces contain only allowed files."""

    @pytest.mark.parametrize("variant", ["A", "B"])
    def test_workspace_has_no_disallowed_files(self, variant: str) -> None:
        ws = TASK_DIR / "variants" / variant / "workspace"
        allowed, disallowed = validate_workspace(ws)
        assert len(disallowed) == 0, f"Disallowed files in {variant}: {disallowed}"
        assert len(allowed) == 5, f"Expected 5 allowed files, got: {allowed}"


class TestT02WorkspaceExport:
    """Validate that export only copies allowed files."""

    @pytest.mark.parametrize("variant", ["A", "B"])
    def test_export_contains_only_allowed(self, variant: str) -> None:
        ws = TASK_DIR / "variants" / variant / "workspace"
        with tempfile.TemporaryDirectory(prefix="atavism_t02_exp_") as tmpdir:
            exported = export_workspace(ws, Path(tmpdir))
            for f in exported:
                assert matches_allowlist(f), f"Exported disallowed file: {f}"
            assert len(exported) == 5

    @pytest.mark.parametrize("variant", ["A", "B"])
    def test_export_creates_expected_files(self, variant: str) -> None:
        ws = TASK_DIR / "variants" / variant / "workspace"
        with tempfile.TemporaryDirectory(prefix="atavism_t02_exp_") as tmpdir:
            out = Path(tmpdir)
            exported = export_workspace(ws, out)
            for f in exported:
                assert (out / f).is_file(), f"Exported file not found: {f}"

