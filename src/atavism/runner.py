"""Controlled Evaluation Runner for Atavism benchmark tasks.

Orchestrates prompt building, provider completions, candidate code extraction,
trial recording, and security-gated grading.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from .execution import ContainerExecutionBackend, TrustLevel, UntrustedExecutionUnavailableError
from .grading import grade_task_candidate
from .providers.base import CompletionRequest, CompletionResponse, ModelProvider
from .providers.free_tier import FreeTierGuard
from .providers.secrets import redact_secrets
from .trials import TrialRecord


def get_git_commit_sha(repo_dir: Path | None = None) -> str:
    """Retrieve current Git commit SHA."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_dir or Path.cwd()),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return "unknown"


def compute_hash(content: str | bytes) -> str:
    """Compute sha256 hash formatted as sha256:<hex>."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def sanitize_name(name: str) -> str:
    """Sanitize model or task names for safe directory and file paths."""
    return re.sub(r"[^a-zA-Z0-9_\-\.]", "_", name)


def extract_python_code(raw_completion: str) -> tuple[str, bool]:
    """Extract Python source code from a model completion.
    
    Returns:
        tuple of (extracted_code, is_syntax_valid)
    """
    text = (raw_completion or "").strip()
    code = ""

    # Check for markdown code blocks with python tag
    py_blocks = re.findall(r"```(?:python|py)\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if py_blocks:
        code = py_blocks[0].strip()
    else:
        # Check for generic code blocks
        generic_blocks = re.findall(r"```\s*\n(.*?)```", text, re.DOTALL)
        if generic_blocks:
            code = generic_blocks[0].strip()
        else:
            code = text

    # Validate Python syntax via AST
    try:
        ast.parse(code)
        return code, True
    except SyntaxError:
        return code, False


def build_trial_prompt(
    task_dir: Path,
    variant: str,
) -> tuple[str, str, dict[str, str], dict[str, Any]]:
    """Construct neutral system and user prompts using only permitted workspace files.
    
    A model never receives:
    - hidden tests (private/tests/)
    - reference implementations (private/reference/)
    - mutation fixtures (private/mutants/)
    - opposing variant files
    - task manifest configuration (task.json)
    
    Returns:
        tuple of (system_prompt, user_prompt, manifest_hashes, execution_info)
    """
    v_upper = variant.upper()
    workspace_dir = task_dir / "variants" / v_upper / "workspace"
    if not workspace_dir.is_dir():
        raise FileNotFoundError(f"Workspace not found for variant {v_upper}: {workspace_dir}")

    task_json_path = task_dir / "task.json"
    if not task_json_path.is_file():
        raise FileNotFoundError(f"task.json not found in {task_dir}")

    with open(task_json_path, "r", encoding="utf-8") as f:
        task_meta = json.load(f)

    exec_info = task_meta.get("execution", {})
    package_name = exec_info.get("package_name", "")
    module_name = exec_info.get("module_name", "")

    # Read model-visible files
    task_md_path = workspace_dir / "TASK.md"
    contract_md_path = workspace_dir / "contract.md"
    types_path = workspace_dir / "src" / package_name / "types.py"
    target_path = workspace_dir / "src" / package_name / module_name

    task_md_text = task_md_path.read_text(encoding="utf-8") if task_md_path.is_file() else ""
    contract_md_text = contract_md_path.read_text(encoding="utf-8") if contract_md_path.is_file() else ""
    types_text = types_path.read_text(encoding="utf-8") if types_path.is_file() else ""
    starter_text = target_path.read_text(encoding="utf-8") if target_path.is_file() else ""

    manifest_hashes = {
        "TASK.md": compute_hash(task_md_text),
        "contract.md": compute_hash(contract_md_text),
        f"src/{package_name}/types.py": compute_hash(types_text),
        f"src/{package_name}/{module_name}": compute_hash(starter_text),
    }

    system_prompt = (
        "You are an expert Python software engineer. Implement the required module adhering strictly "
        "to the provided technical specifications and contract document. Output only the complete "
        "source code for the target implementation file."
    )

    user_prompt = f"""# Technical Task Specification

## Overview
{task_md_text}

## Authoritative Contract Specification (contract.md)
{contract_md_text}

## Type Definitions (src/{package_name}/types.py)
```python
{types_text}
```

## Starter Code (src/{package_name}/{module_name})
```python
{starter_text}
```

## Implementation Instructions
Implement the complete module `{module_name}` in the `{package_name}` package.
Your implementation must adhere strictly to the authoritative rules and error conditions in `contract.md`.
Output only the complete, self-contained Python source code inside a single ```python ... ``` code block.
Do not omit any required imports, classes, functions, or exception handling.
"""

    return system_prompt, user_prompt, manifest_hashes, exec_info


def generate_presentation_schedule(
    tasks: Sequence[str],
    trials: int = 1,
    counterbalance: bool = True,
) -> list[tuple[str, str, int]]:
    """Generate a counterbalanced presentation schedule across tasks and variants."""
    schedule: list[tuple[str, str, int]] = []
    for trial_idx in range(1, trials + 1):
        for task_idx, task in enumerate(tasks):
            if counterbalance and (task_idx + trial_idx) % 2 == 0:
                variants = ("B", "A")
            else:
                variants = ("A", "B")
            for var in variants:
                schedule.append((task, var, trial_idx))
    return schedule


def run_single_trial(
    task_dir: Path,
    variant: str,
    provider: ModelProvider,
    model: str,
    trial_number: int = 1,
    output_base_dir: Path = Path("results/trials"),
    temperature: float = 0.0,
    max_tokens: int = 4096,
    timeout: int = 60,
    dry_run: bool = False,
    trust_level: str = "untrusted",
) -> TrialRecord:
    """Execute or simulate a single model trial under strict experimental controls."""
    if trust_level != TrustLevel.UNTRUSTED.value:
        raise ValueError(
            f"Security violation: trust_level must be '{TrustLevel.UNTRUSTED.value}'. "
            "Untrusted model-generated code cannot be run under 'trusted-local'."
        )

    task_id = task_dir.name.split("_")[0]
    now_utc = datetime.now(timezone.utc)
    timestamp_iso = now_utc.isoformat()
    timestamp_compact = now_utc.strftime("%Y%m%d_%H%M%S")
    sanitized_model = sanitize_name(model)

    trial_id = f"{task_id}-{variant.upper()}-{sanitized_model}-trial{trial_number:02d}-{timestamp_compact}"
    trial_dir = output_base_dir / task_dir.name / variant.upper() / sanitized_model / trial_id
    trial_dir.mkdir(parents=True, exist_ok=True)

    git_sha = get_git_commit_sha()

    # 1. Build prompt and metadata
    sys_prompt, user_prompt, manifest_hashes, exec_info = build_trial_prompt(task_dir, variant)
    pricing = FreeTierGuard.get_pricing_info(model)

    # 2. Dry-Run Handling
    if dry_run:
        print(f"\n[DRY RUN] Trial ID: {trial_id}")
        print(f"  Task:         {task_dir.name} (Variant {variant.upper()})")
        print(f"  Provider:     {provider.provider_name}")
        print(f"  Model ID:     {model}")
        print(f"  Pricing:      {pricing['pricing_classification']} (Expected Cost: $0.00)")
        print(f"  Max Tokens:   {max_tokens} | Temperature: {temperature}")
        print(f"  Prompt Hash:  {compute_hash(user_prompt)}")
        print(f"  Target File:  src/{exec_info.get('package_name')}/{exec_info.get('module_name')}")
        print("  Status:       DRY_RUN completed successfully (0 API calls, 0 code executed).")

        record = TrialRecord(
            trial_id=trial_id,
            timestamp=timestamp_iso,
            task_id=task_dir.name,
            variant=variant.upper(),
            benchmark_commit=git_sha,
            grader_version="1.0.0",
            execution_backend="none (dry_run)",
            trust_level=trust_level,
            trial_status="DRY_RUN",
            model={
                "provider": provider.provider_name,
                "name": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "pricing": pricing,
            },
            manifest_hashes=manifest_hashes,
            execution_metrics={
                "duration_seconds": 0.0,
                "cost_usd": 0.0,
            },
            notes="Dry-run simulation only; zero network requests and zero candidate code executed.",
        )
        record.save(trial_dir)
        return record

    # 3. Model Request Execution
    req = CompletionRequest.from_prompt(
        user_prompt=user_prompt,
        system_prompt=sys_prompt,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
    )

    t0 = time.monotonic()
    response = provider.complete(req)
    total_duration = time.monotonic() - t0

    # 4. Save Transcript (Secrets Redacted)
    transcript_text = (
        f"=== SYSTEM PROMPT ===\n{sys_prompt}\n\n"
        f"=== USER PROMPT ===\n{user_prompt}\n\n"
        f"=== MODEL COMPLETION ===\n{response.content}\n"
    )
    (trial_dir / "transcript.txt").write_text(redact_secrets(transcript_text), encoding="utf-8")

    # 5. Extract Candidate Code
    code, is_syntax_valid = extract_python_code(response.content)
    candidate_path = trial_dir / "candidate.py"
    candidate_path.write_text(code, encoding="utf-8")
    code_hash = compute_hash(code)

    exec_metrics = {
        "duration_seconds": total_duration,
        "latency_seconds": response.latency_seconds,
        "tokens_prompt": response.prompt_tokens,
        "tokens_completion": response.completion_tokens,
        "tokens_total": response.total_tokens,
        "cost_usd": response.cost_usd or 0.0,
    }

    # 6. Syntax Check Failure Handling
    if not is_syntax_valid:
        record = TrialRecord(
            trial_id=trial_id,
            timestamp=timestamp_iso,
            task_id=task_dir.name,
            variant=variant.upper(),
            benchmark_commit=git_sha,
            grader_version="1.0.0",
            execution_backend="container_docker",
            trust_level=trust_level,
            trial_status="SYNTAX_ERROR",
            model={
                "provider": provider.provider_name,
                "name": model,
                "actual_returned_name": response.model_name,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "pricing": pricing,
                "pricing_evidence": getattr(response, "pricing_evidence", {}),
                "routing_metadata": getattr(response, "routing_metadata", {}),
            },
            candidate_code_hash=code_hash,
            manifest_hashes=manifest_hashes,
            grader_result={"passed": False, "total_tests": 0, "errors": 1},
            execution_metrics=exec_metrics,
            failure_category="SYNTAX_ERROR",
            notes="Candidate code extracted from completion failed ast.parse syntax validation.",
        )
        record.save(trial_dir)
        return record

    # 7. Security Gate Enforcement (Phase 7 Non-Negotiable)
    container_backend = ContainerExecutionBackend()
    avail, reason = container_backend.is_available()

    if not avail:
        print(f"\n[SECURITY GATE BLOCKED] Trial ID: {trial_id}")
        print("  Untrusted execution sandbox (Linux container) is unavailable on this host.")
        print(f"  Reason: {reason}")
        print("  Candidate code preserved at candidate.py. Host execution blocked.")

        record = TrialRecord(
            trial_id=trial_id,
            timestamp=timestamp_iso,
            task_id=task_dir.name,
            variant=variant.upper(),
            benchmark_commit=git_sha,
            grader_version="1.0.0",
            execution_backend="container_docker",
            trust_level=trust_level,
            trial_status="SECURITY_BLOCKED",
            model={
                "provider": provider.provider_name,
                "name": model,
                "actual_returned_name": response.model_name,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "pricing": pricing,
                "pricing_evidence": getattr(response, "pricing_evidence", {}),
                "routing_metadata": getattr(response, "routing_metadata", {}),
            },
            candidate_code_hash=code_hash,
            manifest_hashes=manifest_hashes,
            grader_result=None,
            execution_metrics=exec_metrics,
            failure_category="CONTAINER_SANDBOX_UNAVAILABLE",
            notes=(
                f"Candidate code successfully generated and preserved, but execution is blocked "
                f"because OCI container isolation is unavailable on this host ({reason}). "
                "Deploy to Linux host with Docker/Podman to execute untrusted grading."
            ),
        )
        record.save(trial_dir)
        return record

    # 8. Grader Execution (Only reached when container isolation is verified)
    res = grade_task_candidate(
        task_dir=task_dir,
        variant=variant.upper(),
        candidate_path=candidate_path,
        timeout=timeout,
        trust_level=TrustLevel.UNTRUSTED.value,
    )

    failure_cat = None
    if not res.passed:
        if res.timed_out:
            failure_cat = "TIMEOUT"
        else:
            failure_cat = "CONTRACT_REGRESSION"

    grader_result_data = {
        "passed": res.passed,
        "total_tests": res.total_tests,
        "passed_tests": res.passed_tests,
        "failed_tests": res.failed_tests,
        "errors": res.errors,
        "diagnostics": {k: v.score for k, v in res.diagnostics.items()},
        "failure_reasons": list(res.failure_reasons.values())[:5],
    }

    record = TrialRecord(
        trial_id=trial_id,
        timestamp=timestamp_iso,
        task_id=task_dir.name,
        variant=variant.upper(),
        benchmark_commit=git_sha,
        grader_version="1.0.0",
        execution_backend="container_docker",
        trust_level=trust_level,
        trial_status="COMPLETED",
        model={
            "provider": provider.provider_name,
            "name": model,
            "actual_returned_name": response.model_name,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "pricing": pricing,
            "pricing_evidence": getattr(response, "pricing_evidence", {}),
            "routing_metadata": getattr(response, "routing_metadata", {}),
        },
        candidate_code_hash=code_hash,
        manifest_hashes=manifest_hashes,
        grader_result=grader_result_data,
        execution_metrics=exec_metrics,
        failure_category=failure_cat,
        notes="Evaluated via verified OCI container isolation backend.",
    )
    record.save(trial_dir)
    return record

