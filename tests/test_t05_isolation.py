"""Workspace isolation and allowlist tests for Task T05."""

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
TASK_DIR = ROOT / "benchmark" / "tasks" / "T05_event_stream_projection"


class TestT05AllowlistMatching:
    """Verify that allowlist matching correctly classifies files for T05."""

    def test_task_md_allowed(self) -> None:
        assert matches_allowlist("TASK.md")

    def test_contract_md_allowed(self) -> None:
        assert matches_allowlist("contract.md")

    def test_python_source_allowed(self) -> None:
        assert matches_allowlist("src/atavism_projection/__init__.py")
        assert matches_allowlist("src/atavism_projection/types.py")
        assert matches_allowlist("src/atavism_projection/projector.py")

    def test_reference_not_allowed(self) -> None:
        assert not matches_allowlist("private/reference/control.py")
        assert not matches_allowlist("private/reference/treatment.py")

    def test_test_file_not_allowed(self) -> None:
        assert not matches_allowlist("private/tests/common/test_initialization.py")

    def test_conftest_not_allowed(self) -> None:
        assert not matches_allowlist("private/tests/conftest.py")

    def test_mutant_not_allowed(self) -> None:
        assert not matches_allowlist("private/mutants/__init__.py")

    def test_task_json_not_allowed(self) -> None:
        assert not matches_allowlist("task.json")


class TestT05WorkspaceValidation:
    """Verify that existing model workspaces in T05 contain no disallowed files."""

    @pytest.mark.parametrize("variant", ["A", "B"])
    def test_workspace_has_no_disallowed_files(self, variant: str) -> None:
        workspace_dir = TASK_DIR / "variants" / variant / "workspace"
        allowed, disallowed = validate_workspace(workspace_dir)
        assert len(disallowed) == 0, f"Disallowed files found in {variant}: {disallowed}"
        assert len(allowed) == 5


class TestT05ExportIsolation:
    """Verify that exporting workspaces strips private tests, reference solutions, and metadata."""

    @pytest.mark.parametrize("variant", ["A", "B"])
    def test_exported_workspace_contains_only_allowed_files(self, variant: str) -> None:
        with tempfile.TemporaryDirectory() as td:
            target_dir = Path(td) / f"export_{variant}"
            ws_dir = TASK_DIR / "variants" / variant / "workspace"
            manifest = export_workspace(ws_dir, target_dir)

            for rel_path in manifest:
                assert matches_allowlist(rel_path)

            for root, _, files in target_dir.walk():
                for f in files:
                    full_p = root / f
                    rel_p = full_p.relative_to(target_dir).as_posix()
                    assert matches_allowlist(rel_p), f"Export contained disallowed file: {rel_p}"

            assert not (target_dir / "private").exists()
            assert not (target_dir / "task.json").exists()
