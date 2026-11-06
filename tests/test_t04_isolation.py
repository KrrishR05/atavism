"""Workspace isolation and allowlist tests for Task T04."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from atavism.workspace import (
    export_workspace,
    matches_allowlist,
    validate_workspace,
)

ROOT = Path(__file__).resolve().parent.parent
TASK_DIR = ROOT / "benchmark" / "tasks" / "T04_split_tender_refund"


class TestT04AllowlistMatching:
    """Verify that allowlist matching correctly classifies files for T04."""

    def test_task_md_allowed(self) -> None:
        assert matches_allowlist("TASK.md")

    def test_contract_md_allowed(self) -> None:
        assert matches_allowlist("contract.md")

    def test_python_source_allowed(self) -> None:
        assert matches_allowlist("src/atavism_refund/__init__.py")
        assert matches_allowlist("src/atavism_refund/types.py")
        assert matches_allowlist("src/atavism_refund/service.py")

    def test_reference_not_allowed(self) -> None:
        assert not matches_allowlist("private/reference/control.py")
        assert not matches_allowlist("private/reference/treatment.py")

    def test_test_file_not_allowed(self) -> None:
        assert not matches_allowlist("private/tests/common/test_validation.py")

    def test_conftest_not_allowed(self) -> None:
        assert not matches_allowlist("private/tests/conftest.py")

    def test_mutant_not_allowed(self) -> None:
        assert not matches_allowlist("private/mutants/__init__.py")

    def test_task_json_not_allowed(self) -> None:
        assert not matches_allowlist("task.json")


class TestT04WorkspaceValidation:
    """Verify that existing model workspaces in T04 contain no disallowed files."""

    @pytest.mark.parametrize("variant", ["A", "B"])
    def test_workspace_has_no_disallowed_files(self, variant: str) -> None:
        workspace_dir = TASK_DIR / "variants" / variant / "workspace"
        allowed, disallowed = validate_workspace(workspace_dir)
        assert len(disallowed) == 0, f"Disallowed files found in {variant}: {disallowed}"
        assert len(allowed) == 5


class TestT04WorkspaceExport:
    """Verify that export produces clean workspaces containing only allowed files."""

    @pytest.mark.parametrize("variant", ["A", "B"])
    def test_export_contains_only_allowed(self, variant: str) -> None:
        workspace_dir = TASK_DIR / "variants" / variant / "workspace"
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / f"export_{variant}"
            exported = export_workspace(workspace_dir, output_dir)
            assert len(exported) == 5
            for f in exported:
                assert matches_allowlist(f), f"Disallowed file exported: {f}"

    @pytest.mark.parametrize("variant", ["A", "B"])
    def test_export_creates_expected_files(self, variant: str) -> None:
        workspace_dir = TASK_DIR / "variants" / variant / "workspace"
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / f"export_{variant}"
            export_workspace(workspace_dir, output_dir)
            assert (output_dir / "TASK.md").is_file()
            assert (output_dir / "contract.md").is_file()
            assert (output_dir / "src" / "atavism_refund" / "__init__.py").is_file()
            assert (output_dir / "src" / "atavism_refund" / "types.py").is_file()
            assert (output_dir / "src" / "atavism_refund" / "service.py").is_file()
