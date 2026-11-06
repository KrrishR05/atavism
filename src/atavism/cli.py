"""CLI entry point for Atavism benchmark operations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate task structure and workspace isolation."""
    from atavism.workspace import validate_workspace

    task_dir = Path(args.task_dir)
    if not task_dir.is_dir():
        print(f"Error: Task directory not found: {task_dir}", file=sys.stderr)
        return 1

    exit_code = 0
    for variant in ("A", "B"):
        workspace = task_dir / "variants" / variant / "workspace"
        if not workspace.is_dir():
            print(f"Warning: Variant {variant} workspace not found: {workspace}")
            continue

        allowed, disallowed = validate_workspace(workspace)
        print(f"\nVariant {variant}:")
        print(f"  Allowed files ({len(allowed)}):")
        for f in allowed:
            print(f"    [+] {f}")
        if disallowed:
            print(f"  DISALLOWED files ({len(disallowed)}):")
            for f in disallowed:
                print(f"    [-] {f}")
            exit_code = 1
        else:
            print("  No disallowed files found.")

    return exit_code


def cmd_export(args: argparse.Namespace) -> int:
    """Export a model workspace."""
    from atavism.workspace import export_workspace

    workspace_dir = Path(args.workspace_dir)
    output_dir = Path(args.output_dir)

    try:
        exported = export_workspace(workspace_dir, output_dir)
        print(f"Exported {len(exported)} files to {output_dir}:")
        for f in exported:
            print(f"  {f}")
        return 0
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_info(args: argparse.Namespace) -> int:
    """Show task information."""
    task_json = Path(args.task_dir) / "task.json"
    if not task_json.is_file():
        print(f"Error: task.json not found in {args.task_dir}", file=sys.stderr)
        return 1

    with open(task_json) as f:
        info = json.load(f)

    print(f"Task: {info['id']} — {info['name']}")
    print(f"Dimension: {info.get('dimension', 'N/A')}")
    print(f"Description: {info.get('description', 'N/A')}")
    print(f"Experimental variable: {info.get('experimental_variable', 'N/A')}")
    print(f"Variants:")
    for vid, vdata in info.get("variants", {}).items():
        print(f"  {vid}: {vdata.get('label', '?')} — {vdata.get('description', '?')}")

    return 0


def cmd_grade(args: argparse.Namespace) -> int:
    """Grade a candidate implementation for a task variant."""
    from atavism.grading import grade_task_candidate

    task_dir = Path(args.task_dir)
    variant = args.variant.upper()
    candidate_path = Path(args.candidate)

    if not task_dir.is_dir():
        print(f"Error: Task directory not found: {task_dir}", file=sys.stderr)
        return 1
    if not candidate_path.is_file():
        print(f"Error: Candidate file not found: {candidate_path}", file=sys.stderr)
        return 1

    try:
        result = grade_task_candidate(
            task_dir,
            variant,
            candidate_path,
            timeout=args.timeout,
            trust_level=args.trust_level,
        )
    except Exception as e:
        print(f"Error executing grader: {e}", file=sys.stderr)
        return 1

    status_str = "PASSED" if result.passed else "FAILED"
    print(f"\nGrading Result: {status_str}")
    print(f"  Total tests:  {result.total_tests}")
    print(f"  Passed tests: {result.passed_tests}")
    print(f"  Failed tests: {result.failed_tests}")
    print(f"  Errors:       {result.errors}")

    if result.diagnostics:
        print("\nDiagnostics:")
        for name, diag in result.diagnostics.items():
            mark = "[PASS]" if diag.passed_all else "[FAIL]"
            pct = f"{diag.score * 100:.1f}%"
            print(f"  {mark} {name}: {diag.passed}/{diag.total} passed ({pct})")

    if not result.passed and result.failure_reasons:
        print("\nFailures:")
        for test_name, reason in list(result.failure_reasons.items())[:5]:
            first_line = reason.splitlines()[0] if reason else "Assertion failed"
            print(f"  [-] {test_name}: {first_line}")

    return 0 if result.passed else 2


def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="atavism",
        description="Atavism — AI Evaluation Benchmark CLI",
    )
    sub = parser.add_subparsers(dest="command")

    # validate
    val = sub.add_parser("validate", help="Validate task structure and workspace isolation")
    val.add_argument("task_dir", help="Path to task directory")

    # export
    exp = sub.add_parser("export", help="Export a clean model workspace")
    exp.add_argument("workspace_dir", help="Path to workspace directory")
    exp.add_argument("output_dir", help="Output directory for export")

    # info
    inf = sub.add_parser("info", help="Show task information")
    inf.add_argument("task_dir", help="Path to task directory")

    # grade
    grd = sub.add_parser("grade", help="Grade a candidate implementation")
    grd.add_argument("task_dir", help="Path to task directory")
    grd.add_argument("variant", help="Variant identifier (A or B)")
    grd.add_argument("candidate", help="Path to candidate file")
    grd.add_argument("--timeout", type=int, default=60, help="Test execution timeout in seconds")
    grd.add_argument(
        "--trust-level",
        choices=["untrusted", "trusted-local"],
        default="untrusted",
        help="Trust level for execution: 'untrusted' requires container sandbox (default); 'trusted-local' runs in un-sandboxed host environment",
    )

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    commands = {
        "validate": cmd_validate,
        "export": cmd_export,
        "info": cmd_info,
        "grade": cmd_grade,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())

