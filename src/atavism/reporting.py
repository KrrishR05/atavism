"""Reporting — aggregation and analysis of trial results.

Provides utilities for computing pass rates, pass@k, pass^k,
comparing control vs. treatment performance, and generating benchmark summary reports.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class VariantSummary:
    """Summary statistics for a single variant."""
    variant: str
    total_trials: int
    passed_trials: int
    pass_rate: float


def compute_pass_rate(passed: int, total: int) -> float:
    """Compute simple pass rate."""
    if total == 0:
        return 0.0
    return passed / total


def compute_pass_at_k(n: int, c: int, k: int) -> float:
    """Compute pass@k: probability at least 1 of k samples passes."""
    if n == 0 or k == 0:
        return 0.0
    if c == n:
        return 1.0
    if c == 0:
        return 0.0

    log_numerator = sum(math.log(n - c - i) for i in range(k) if n - c - i > 0)
    log_denominator = sum(math.log(n - i) for i in range(k))

    if k > n - c:
        return 1.0

    return 1.0 - math.exp(log_numerator - log_denominator)


def compute_pass_pow_k(pass_rate: float, k: int) -> float:
    """Compute pass^k: probability all k samples pass."""
    return pass_rate ** k


def compare_variants(
    control: VariantSummary,
    treatment: VariantSummary,
) -> dict[str, object]:
    """Compare control vs. treatment performance."""
    delta = treatment.pass_rate - control.pass_rate
    return {
        "control_pass_rate": control.pass_rate,
        "treatment_pass_rate": treatment.pass_rate,
        "delta": delta,
        "control_trials": control.total_trials,
        "treatment_trials": treatment.total_trials,
    }


def find_trial_records(results_dir: Path) -> list[dict[str, Any]]:
    """Recursively discover and load all metadata.json files in a results directory."""
    records: list[dict[str, Any]] = []
    if not results_dir.is_dir():
        return records

    for meta_path in sorted(results_dir.rglob("metadata.json")):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                records.append(data)
        except Exception:
            continue
    return records


def aggregate_evaluation_results(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate a collection of trial records into structured benchmark metrics."""
    total_records = len(records)
    by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_status: dict[str, int] = defaultdict(int)
    by_failure: dict[str, int] = defaultdict(int)

    for r in records:
        model_name = r.get("model", {}).get("name") or "unknown"
        by_model[model_name].append(r)
        status = r.get("trial_status", "UNKNOWN")
        by_status[status] += 1
        fail_cat = r.get("failure_category")
        if fail_cat:
            by_failure[fail_cat] += 1

    model_summaries: dict[str, Any] = {}
    for model_name, model_records in by_model.items():
        # Group by task and variant
        cells: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: {"A": [], "B": []})
        for rec in model_records:
            task = rec.get("task_id", "unknown")
            variant = rec.get("variant", "unknown").upper()
            cells[task][variant].append(rec)

        task_metrics: dict[str, Any] = {}
        for task, vars_dict in sorted(cells.items()):
            a_recs = vars_dict["A"]
            b_recs = vars_dict["B"]

            a_passed = sum(1 for r in a_recs if (r.get("grader_result") or {}).get("passed") is True)
            b_passed = sum(1 for r in b_recs if (r.get("grader_result") or {}).get("passed") is True)

            a_rate = compute_pass_rate(a_passed, len(a_recs))
            b_rate = compute_pass_rate(b_passed, len(b_recs))
            delta = b_rate - a_rate

            task_metrics[task] = {
                "variant_A": {"total": len(a_recs), "passed": a_passed, "pass_rate": a_rate},
                "variant_B": {"total": len(b_recs), "passed": b_passed, "pass_rate": b_rate},
                "delta": delta,
            }

        total_trials = len(model_records)
        completed_trials = sum(1 for r in model_records if r.get("trial_status") == "COMPLETED")
        passed_trials = sum(1 for r in model_records if (r.get("grader_result") or {}).get("passed") is True)
        overall_pass_rate = compute_pass_rate(passed_trials, completed_trials) if completed_trials > 0 else 0.0

        model_summaries[model_name] = {
            "total_trials": total_trials,
            "completed_trials": completed_trials,
            "passed_trials": passed_trials,
            "overall_pass_rate": overall_pass_rate,
            "tasks": task_metrics,
        }

    return {
        "total_records": total_records,
        "status_distribution": dict(by_status),
        "failure_distribution": dict(by_failure),
        "models": model_summaries,
    }


def format_markdown_report(aggregated: dict[str, Any]) -> str:
    """Format aggregated evaluation metrics into a GitHub-flavored markdown report."""
    lines: list[str] = [
        "# Atavism — Model Evaluation Summary Report",
        "",
        f"**Total Trial Records Analyzed:** {aggregated['total_records']}",
        "",
        "## 1. Execution Status Distribution",
        "",
        "| Execution Status | Count | Notes |",
        "| :--- | :---: | :--- |",
    ]

    for status, count in sorted(aggregated.get("status_distribution", {}).items()):
        note = "Evaluated via container sandbox" if status == "COMPLETED" else (
            "Untrusted candidate code preserved; execution blocked on non-container host" if status == "SECURITY_BLOCKED" else (
                "Simulated trial without API or code execution" if status == "DRY_RUN" else "Code syntax error"
            )
        )
        lines.append(f"| `{status}` | {count} | {note} |")

    lines.extend([
        "",
        "## 2. Model Performance & Matched-Pair Analysis",
        "",
    ])

    for model_name, summary in aggregated.get("models", {}).items():
        lines.extend([
            f"### Model: `{model_name}`",
            f"- **Total Trials:** {summary['total_trials']} (Completed: {summary['completed_trials']})",
            f"- **Overall Pass Rate:** {summary['overall_pass_rate'] * 100:.1f}%",
            "",
            r"| Task ID | Variant A (Control) | Variant B (Treatment) | Delta ($\Delta = B - A$) |",
            "| :--- | :---: | :---: | :---: |",
        ])

        for task_id, tdata in sorted(summary.get("tasks", {}).items()):
            a_data = tdata["variant_A"]
            b_data = tdata["variant_B"]
            a_str = f"{a_data['passed']}/{a_data['total']} ({a_data['pass_rate'] * 100:.1f}%)" if a_data["total"] > 0 else "N/A"
            b_str = f"{b_data['passed']}/{b_data['total']} ({b_data['pass_rate'] * 100:.1f}%)" if b_data["total"] > 0 else "N/A"
            delta_str = f"{tdata['delta'] * 100:+.1f}%" if a_data["total"] > 0 and b_data["total"] > 0 else "N/A"
            lines.append(f"| `{task_id}` | {a_str} | {b_str} | {delta_str} |")
        lines.append("")

    if aggregated.get("failure_distribution"):
        lines.extend([
            "## 3. Failure Taxonomy Breakdown",
            "",
            "| Failure Category | Occurrences |",
            "| :--- | :---: |",
        ])
        for cat, count in sorted(aggregated["failure_distribution"].items()):
            lines.append(f"| `{cat}` | {count} |")
        lines.append("")

    return "\n".join(lines)
