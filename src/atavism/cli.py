"""CLI entry point for Atavism benchmark operations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BENCHMARK_TASKS_DIR = Path(__file__).resolve().parent.parent.parent / "benchmark" / "tasks"


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


def _resolve_task_dirs(task_arg: str) -> list[Path]:
    """Resolve task directories from 'all', task ID ('T01'), or path."""
    if task_arg.lower() in ("all", "*"):
        return sorted(p for p in BENCHMARK_TASKS_DIR.iterdir() if p.is_dir() and (p / "task.json").is_file())

    path = Path(task_arg)
    if path.is_dir() and (path / "task.json").is_file():
        return [path]

    # Try matching prefix under benchmark/tasks/
    matches = [
        p for p in BENCHMARK_TASKS_DIR.iterdir()
        if p.is_dir() and p.name.upper().startswith(task_arg.upper())
    ]
    if matches:
        return sorted(matches)

    print(f"Error: Could not resolve task '{task_arg}'.", file=sys.stderr)
    return []


def cmd_eval(args: argparse.Namespace) -> int:
    """Run controlled model evaluations across tasks and variants."""
    from atavism.providers import FreeTierGuard, NonFreeModelError, get_provider
    from atavism.runner import generate_presentation_schedule, run_single_trial

    model_id = args.model
    # Strict Cost Guard: Enforce verified free-tier models ($0.00 budget)
    try:
        FreeTierGuard.assert_free(model_id)
    except NonFreeModelError as err:
        print(f"Budget Error: {err}", file=sys.stderr)
        return 1

    task_dirs = _resolve_task_dirs(args.task)
    if not task_dirs:
        return 1

    provider = get_provider(
        name=args.provider,
        default_model=model_id,
        enforce_free_tier=True,
    )

    variants = ["A", "B"] if args.variant.lower() in ("both", "all") else [args.variant.upper()]
    task_names = [td.name for td in task_dirs]
    schedule = generate_presentation_schedule(task_names, trials=args.trials, counterbalance=True)
    # Filter schedule for selected variants
    schedule = [item for item in schedule if item[1] in variants]

    output_dir = Path(args.output_dir)
    print("=" * 80)
    print("ATAVISM CONTROLLED MODEL EVALUATION")
    print("=" * 80)
    print(f"Provider:        {provider.provider_name}")
    print(f"Model ID:        {model_id}")
    print(f"Cost Guard:      FREE TIER ONLY ($0.00 Budget Authorized)")
    print(f"Tasks Selected:  {len(task_dirs)} ({', '.join(task_names)})")
    print(f"Variants:        {', '.join(variants)}")
    print(f"Trials / Cell:   {args.trials}")
    print(f"Total Trials:    {len(schedule)}")
    print(f"Execution Mode:  {'DRY RUN (No network calls or code execution)' if args.dry_run else 'LIVE EVALUATION'}")
    print(f"Trust Level:     untrusted (Linux container isolation required for grading)")
    print(f"Output Directory:{output_dir}")
    print("=" * 80)

    results = []
    for tname, var, trial_idx in schedule:
        td = next(p for p in task_dirs if p.name == tname)
        try:
            record = run_single_trial(
                task_dir=td,
                variant=var,
                provider=provider,
                model=model_id,
                trial_number=trial_idx,
                output_base_dir=output_dir,
                temperature=args.temperature,
                max_tokens=args.max_tokens,
                timeout=args.timeout,
                dry_run=args.dry_run,
                trust_level="untrusted",
            )
            results.append(record)
        except Exception as exc:
            print(f"Error during trial ({tname}-{var}-{trial_idx}): {exc}", file=sys.stderr)

    print("\n" + "=" * 80)
    print(f"Evaluation finished: {len(results)}/{len(schedule)} trials processed.")
    print("=" * 80)
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    """Aggregate evaluation trial results and generate summary reports."""
    from atavism.reporting import aggregate_evaluation_results, find_trial_records, format_markdown_report

    results_dir = Path(args.results_dir)
    records = find_trial_records(results_dir)
    if not records:
        print(f"No trial records found in '{results_dir}'. Run 'atavism eval' first.")
        return 0

    aggregated = aggregate_evaluation_results(records)
    md_report = format_markdown_report(aggregated)

    print(md_report)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(md_report, encoding="utf-8")
        print(f"\nMarkdown report written to: {out_path}")

    if args.json_output:
        json_path = Path(args.json_output)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(aggregated, f, indent=2)
        print(f"JSON metrics written to: {json_path}")

    return 0


def cmd_models(args: argparse.Namespace) -> int:
    """Display supported verified zero-cost free-tier models and provider status."""
    from atavism.providers import VERIFIED_FREE_MODELS, get_provider

    provider = get_provider(name=args.provider)
    conn_ok, conn_msg = provider.check_connection()

    print("=" * 80)
    print("ATAVISM — SUPPORTED ZERO-COST FREE-TIER MODELS")
    print("=" * 80)
    print(f"Provider:          {provider.provider_name}")
    print(f"Connection Status: {'CONNECTED' if conn_ok else 'NOT CONNECTED'}")
    print(f"Details:           {conn_msg}")
    print(f"Budget Rule:       STRICT ZERO-COST ($0.00). Paid models are rejected.")
    print("-" * 80)
    print("Verified Free Models (carry explicit ':free' suffix):")
    for m in VERIFIED_FREE_MODELS:
        print(f"  [FREE] {m}")
    print("=" * 80)
    return 0


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

    # eval
    evl = sub.add_parser("eval", help="Run controlled model evaluations")
    evl.add_argument("--task", default="all", help="Task ID (e.g. 'T01') or 'all' for all 5 tasks")
    evl.add_argument("--variant", default="both", choices=["A", "B", "both", "all"], help="Variant to evaluate")
    evl.add_argument("--model", default="meta-llama/llama-3.3-70b-instruct:free", help="Verified free-tier model identifier")
    evl.add_argument("--provider", default="openrouter", help="Provider adapter ('openrouter')")
    evl.add_argument("--trials", type=int, default=1, help="Number of trials per task/variant cell")
    evl.add_argument("--temperature", type=float, default=0.0, help="Sampling temperature")
    evl.add_argument("--max-tokens", type=int, default=4096, help="Maximum completion tokens")
    evl.add_argument("--timeout", type=int, default=60, help="Provider request timeout in seconds")
    evl.add_argument("--dry-run", action="store_true", help="Simulate trial execution without network requests or code execution")
    evl.add_argument("--output-dir", default="results/trials", help="Directory where trial records are persisted")

    # report
    rep = sub.add_parser("report", help="Aggregate evaluation trial records and produce summary reports")
    rep.add_argument("--results-dir", default="results/trials", help="Directory containing metadata.json files")
    rep.add_argument("--output", help="Optional path to output markdown summary")
    rep.add_argument("--json-output", help="Optional path to output JSON summary")

    # models
    mod = sub.add_parser("models", help="List verified zero-cost free-tier models")
    mod.add_argument("--provider", default="openrouter", help="Provider adapter ('openrouter')")

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    commands = {
        "validate": cmd_validate,
        "export": cmd_export,
        "info": cmd_info,
        "grade": cmd_grade,
        "eval": cmd_eval,
        "report": cmd_report,
        "models": cmd_models,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
