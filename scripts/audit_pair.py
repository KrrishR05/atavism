"""Pair audit — detect unintended differences between task variants.

Compares the A and B workspace directories to ensure the only
differences are the intended experimental variables.
"""

from __future__ import annotations

import difflib
import json
import sys
from pathlib import Path

# Fallback files expected to differ between variants if not specified in task.json
DEFAULT_EXPECTED_DIFF_FILES = frozenset({"contract.md"})


def audit_pair(task_dir: Path) -> dict[str, object]:
    """Audit a paired task for unintended differences.

    Args:
        task_dir: Path to the task directory (e.g., T01_retry_semantics/).

    Returns:
        Dict with audit results including intended and unintended differences.
    """
    ws_a = task_dir / "variants" / "A" / "workspace"
    ws_b = task_dir / "variants" / "B" / "workspace"

    if not ws_a.is_dir():
        raise FileNotFoundError(f"Variant A workspace not found: {ws_a}")
    if not ws_b.is_dir():
        raise FileNotFoundError(f"Variant B workspace not found: {ws_b}")

    # Load task-specific expected diff files from task.json
    task_json_path = task_dir / "task.json"
    expected_diff_files: set[str] = set()
    if task_json_path.is_file():
        try:
            with open(task_json_path, encoding="utf-8") as f:
                task_data = json.load(f)
            if "expected_diff_files" in task_data:
                expected_diff_files = set(task_data["expected_diff_files"])
        except Exception:
            pass

    if not expected_diff_files:
        expected_diff_files = set(DEFAULT_EXPECTED_DIFF_FILES)

    files_a = {
        p.relative_to(ws_a).as_posix()
        for p in ws_a.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and not p.name.endswith(".pyc")
    }
    files_b = {
        p.relative_to(ws_b).as_posix()
        for p in ws_b.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and not p.name.endswith(".pyc")
    }

    only_in_a = sorted(files_a - files_b)
    only_in_b = sorted(files_b - files_a)
    common = sorted(files_a & files_b)

    intended_diffs: dict[str, list[str]] = {}
    unintended_diffs: dict[str, list[str]] = {}
    identical_files: list[str] = []

    for rel in common:
        content_a = (ws_a / rel).read_text(encoding="utf-8")
        content_b = (ws_b / rel).read_text(encoding="utf-8")

        if content_a == content_b:
            identical_files.append(rel)
        else:
            diff = list(difflib.unified_diff(
                content_a.splitlines(keepends=True),
                content_b.splitlines(keepends=True),
                fromfile=f"A/{rel}",
                tofile=f"B/{rel}",
            ))
            diff_text = diff

            if rel in expected_diff_files:
                intended_diffs[rel] = diff_text
            else:
                unintended_diffs[rel] = diff_text

    return {
        "task_dir": str(task_dir),
        "files_only_in_a": only_in_a,
        "files_only_in_b": only_in_b,
        "identical_files": identical_files,
        "intended_diffs": intended_diffs,
        "unintended_diffs": unintended_diffs,
        "clean": len(only_in_a) == 0 and len(only_in_b) == 0 and len(unintended_diffs) == 0,
    }


def print_audit_report(result: dict[str, object]) -> None:
    """Print a human-readable audit report."""
    print(f"Pair Audit: {result['task_dir']}")
    print("=" * 60)

    if result["files_only_in_a"]:
        print(f"\n[!] Files only in variant A:")
        for f in result["files_only_in_a"]:
            print(f"  - {f}")

    if result["files_only_in_b"]:
        print(f"\n[!] Files only in variant B:")
        for f in result["files_only_in_b"]:
            print(f"  - {f}")

    if result["identical_files"]:
        print(f"\n[OK] Identical files ({len(result['identical_files'])}):")
        for f in result["identical_files"]:
            print(f"  {f}")

    if result["intended_diffs"]:
        print(f"\n[OK] Intended differences ({len(result['intended_diffs'])}):")
        for filename, diff_lines in result["intended_diffs"].items():
            print(f"\n  {filename}:")
            for line in diff_lines:
                print(f"    {line}", end="")

    if result["unintended_diffs"]:
        print(f"\n[X] UNINTENDED differences ({len(result['unintended_diffs'])}):")
        for filename, diff_lines in result["unintended_diffs"].items():
            print(f"\n  {filename}:")
            for line in diff_lines:
                print(f"    {line}", end="")

    print()
    if result["clean"]:
        print("[PASS] - No unintended differences detected.")
    else:
        print("[FAIL] - Unintended differences found.")


def main() -> int:
    """CLI entry point for pair audit."""
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <task_directory>")
        print(f"Example: python {sys.argv[0]} benchmark/tasks/T01_retry_semantics")
        return 1

    task_dir = Path(sys.argv[1])
    try:
        result = audit_pair(task_dir)
        print_audit_report(result)
        return 0 if result["clean"] else 1
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
