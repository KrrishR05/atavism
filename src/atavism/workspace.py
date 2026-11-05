"""Workspace isolation — safe export of model workspaces.

Ensures that only permitted files are exported to the model,
preventing leakage of reference solutions, tests, or grader code.
"""

from __future__ import annotations

import fnmatch
import shutil
from pathlib import Path

# Files allowed in a model workspace export.
DEFAULT_ALLOWLIST = [
    "TASK.md",
    "contract.md",
    "src/**/*.py",
]


def matches_allowlist(relative_path: str, allowlist: list[str] | None = None) -> bool:
    """Check if a relative path matches any pattern in the allowlist."""
    patterns = allowlist or DEFAULT_ALLOWLIST
    rel = relative_path.replace("\\", "/")
    for pattern in patterns:
        if fnmatch.fnmatch(rel, pattern):
            return True
    return False


def list_workspace_files(workspace_dir: Path) -> list[Path]:
    """List all files in a workspace directory, excluding Python bytecode caches."""
    if not workspace_dir.is_dir():
        raise FileNotFoundError(f"Workspace directory not found: {workspace_dir}")
    return sorted(
        p for p in workspace_dir.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and not p.name.endswith(".pyc")
    )


def validate_workspace(
    workspace_dir: Path,
    allowlist: list[str] | None = None,
) -> tuple[list[str], list[str]]:
    """Validate that a workspace contains only allowed files.

    Returns:
        A tuple of (allowed_files, disallowed_files) as relative path strings.
    """
    allowed: list[str] = []
    disallowed: list[str] = []
    for filepath in list_workspace_files(workspace_dir):
        rel = filepath.relative_to(workspace_dir).as_posix()
        if matches_allowlist(rel, allowlist):
            allowed.append(rel)
        else:
            disallowed.append(rel)
    return allowed, disallowed


def export_workspace(
    workspace_dir: Path,
    output_dir: Path,
    allowlist: list[str] | None = None,
) -> list[str]:
    """Export a workspace to output_dir, copying only allowed files.

    Returns:
        List of relative paths that were exported.
    """
    if not workspace_dir.is_dir():
        raise FileNotFoundError(f"Workspace directory not found: {workspace_dir}")

    exported: list[str] = []
    for filepath in list_workspace_files(workspace_dir):
        rel = filepath.relative_to(workspace_dir).as_posix()
        if matches_allowlist(rel, allowlist):
            dest = output_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(filepath, dest)
            exported.append(rel)

    return exported

