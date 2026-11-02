"""Tests for workspace isolation — ensuring private files are not exported."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from atavism.workspace import export_workspace, matches_allowlist, validate_workspace

TASK_DIR = Path(__file__).resolve().parent.parent / "benchmark" / "tasks" / "T01_retry_semantics"


class TestAllowlistMatching:
    """Test the file allowlist pattern matching."""

    def test_task_md_allowed(self) -> None:
        assert matches_allowlist("TASK.md")

    def test_contract_md_allowed(self) -> None:
        assert matches_allowlist("contract.md")

    def test_python_source_allowed(self) -> None:
        assert matches_allowlist("src/atavism_retry/client.py")
        assert matches_allowlist("src/atavism_retry/types.py")
        assert matches_allowlist("src/atavism_retry/__init__.py")

    def test_reference_not_allowed(self) -> None:
        assert not matches_allowlist("private/reference/control.py")

    def test_test_file_not_allowed(self) -> None:
        assert not matches_allowlist("private/tests/common/test_common.py")

    def test_conftest_not_allowed(self) -> None:
        assert not matches_allowlist("private/tests/conftest.py")

    def test_mutant_not_allowed(self) -> None:
        assert not matches_allowlist("private/mutants/__init__.py")

    def test_task_json_not_allowed(self) -> None:
        assert not matches_allowlist("task.json")

    def test_random_file_not_allowed(self) -> None:
        assert not matches_allowlist("notes.txt")
        assert not matches_allowlist("secret.py")


class TestWorkspaceValidation:
    """Validate that workspaces contain only allowed files."""

    @pytest.mark.parametrize("variant", ["A", "B"])
    def test_workspace_has_no_disallowed_files(self, variant: str) -> None:
        ws = TASK_DIR / "variants" / variant / "workspace"
        allowed, disallowed = validate_workspace(ws)
        assert len(disallowed) == 0, f"Disallowed files in {variant}: {disallowed}"
        assert len(allowed) > 0, f"No allowed files in {variant}"


class TestWorkspaceExport:
    """Validate that export only copies allowed files."""

    @pytest.mark.parametrize("variant", ["A", "B"])
    def test_export_contains_only_allowed(self, variant: str) -> None:
        ws = TASK_DIR / "variants" / variant / "workspace"
        with tempfile.TemporaryDirectory(prefix="atavism_export_test_") as tmpdir:
            exported = export_workspace(ws, Path(tmpdir))
            for f in exported:
                assert matches_allowlist(f), f"Exported disallowed file: {f}"

    @pytest.mark.parametrize("variant", ["A", "B"])
    def test_export_creates_files(self, variant: str) -> None:
        ws = TASK_DIR / "variants" / variant / "workspace"
        with tempfile.TemporaryDirectory(prefix="atavism_export_test_") as tmpdir:
            output = Path(tmpdir)
            exported = export_workspace(ws, output)
            for f in exported:
                assert (output / f).is_file(), f"Exported file not found: {f}"

