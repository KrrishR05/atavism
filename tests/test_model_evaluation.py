"""Unit tests for controlled evaluation runner, prompt isolation, and trial recording."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from atavism.execution import TrustLevel
from atavism.providers import CompletionRequest, CompletionResponse, ModelProvider
from atavism.reporting import aggregate_evaluation_results, find_trial_records, format_markdown_report
from atavism.runner import (
    build_trial_prompt,
    extract_python_code,
    generate_presentation_schedule,
    run_single_trial,
)
from atavism.trials import TrialRecord

ROOT = Path(__file__).resolve().parent.parent
BENCHMARK_TASKS_DIR = ROOT / "benchmark" / "tasks"


class FakeMockProvider(ModelProvider):
    """Deterministic mock provider for unit testing without network calls."""

    def __init__(self, response_text: str = "def solve(): pass") -> None:
        self.response_text = response_text
        self.call_count = 0
        self.last_request: CompletionRequest | None = None

    @property
    def provider_name(self) -> str:
        return "fake_provider"

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        self.call_count += 1
        self.last_request = request
        return CompletionResponse(
            content=self.response_text,
            model_name=request.model,
            provider=self.provider_name,
            prompt_tokens=100,
            completion_tokens=25,
            total_tokens=125,
            cost_usd=0.0,
            latency_seconds=0.15,
            finish_reason="stop",
        )

    def check_connection(self) -> tuple[bool, str]:
        return True, "Mock connected"


class TestCodeExtraction:
    """Verify robust Python extraction from markdown code fences and raw text."""

    def test_extract_python_markdown_fence(self) -> None:
        raw = "Here is the code:\n```python\ndef add(a, b):\n    return a + b\n```\nHope this helps!"
        code, valid = extract_python_code(raw)
        assert valid is True
        assert code == "def add(a, b):\n    return a + b"

    def test_extract_generic_markdown_fence(self) -> None:
        raw = "```\ndef multiply(x, y):\n    return x * y\n```"
        code, valid = extract_python_code(raw)
        assert valid is True
        assert code == "def multiply(x, y):\n    return x * y"

    def test_extract_raw_python(self) -> None:
        raw = "class MyService:\n    pass"
        code, valid = extract_python_code(raw)
        assert valid is True
        assert code == "class MyService:\n    pass"

    def test_extract_invalid_syntax_flags_false(self) -> None:
        raw = "```python\ndef incomplete_func(\n```"
        code, valid = extract_python_code(raw)
        assert valid is False
        assert "def incomplete_func(" in code


class TestPromptConstructionAndIsolation:
    """Verify that model prompts receive only allowed files and zero private test fixtures."""

    @pytest.mark.parametrize("task_name", ["T01_retry_semantics", "T02_pagination_authority", "T03_tenant_idempotency", "T04_split_tender_refund", "T05_event_stream_projection"])
    @pytest.mark.parametrize("variant", ["A", "B"])
    def test_prompt_isolation_excludes_private_fixtures(self, task_name: str, variant: str) -> None:
        task_dir = BENCHMARK_TASKS_DIR / task_name
        sys_prompt, user_prompt, hashes, exec_info = build_trial_prompt(task_dir, variant)

        # 1. System prompt is neutral
        assert "expert Python software engineer" in sys_prompt

        # 2. Must not contain private grader keywords or test definitions
        assert "test_" not in user_prompt.lower() or "test_paths" not in user_prompt
        assert "def test_" not in user_prompt
        assert "mutant_" not in user_prompt
        assert "conftest" not in user_prompt

        # 3. Must contain model-visible files
        assert "contract.md" in user_prompt
        assert "TASK.md" in hashes
        assert "contract.md" in hashes

        # 4. Target module info is present
        assert exec_info["package_name"] in user_prompt
        assert exec_info["module_name"] in user_prompt


class TestPresentationScheduling:
    """Verify counterbalanced scheduling across tasks and variants."""

    def test_counterbalanced_presentation_alternates_variants(self) -> None:
        tasks = ["T01", "T02", "T03"]
        sched = generate_presentation_schedule(tasks, trials=1, counterbalance=True)
        assert len(sched) == 6
        # Expected alternation: T01: A, B; T02: B, A; T03: A, B
        assert sched[0] == ("T01", "A", 1)
        assert sched[1] == ("T01", "B", 1)
        assert sched[2] == ("T02", "B", 1)
        assert sched[3] == ("T02", "A", 1)
        assert sched[4] == ("T03", "A", 1)
        assert sched[5] == ("T03", "B", 1)


class TestControlledRunnerExecutionAndSecurityGate:
    """Verify execution runner, dry-run mode, and security gate fail-closed enforcement."""

    def test_trust_level_trusted_local_rejected(self, tmp_path: Path) -> None:
        provider = FakeMockProvider()
        task_dir = BENCHMARK_TASKS_DIR / "T01_retry_semantics"

        with pytest.raises(ValueError) as exc:
            run_single_trial(
                task_dir=task_dir,
                variant="A",
                provider=provider,
                model="meta-llama/llama-3.3-70b-instruct:free",
                output_base_dir=tmp_path,
                trust_level="trusted-local",
            )
        assert "trust_level must be 'untrusted'" in str(exc.value)

    def test_dry_run_records_metadata_without_calling_provider(self, tmp_path: Path) -> None:
        provider = FakeMockProvider()
        task_dir = BENCHMARK_TASKS_DIR / "T01_retry_semantics"

        rec = run_single_trial(
            task_dir=task_dir,
            variant="A",
            provider=provider,
            model="meta-llama/llama-3.3-70b-instruct:free",
            output_base_dir=tmp_path,
            dry_run=True,
        )

        assert rec.trial_status == "DRY_RUN"
        assert provider.call_count == 0
        meta_files = list(tmp_path.rglob("metadata.json"))
        assert len(meta_files) == 1
        loaded = TrialRecord.load(meta_files[0])
        assert loaded.trial_status == "DRY_RUN"

    def test_security_gate_blocks_candidate_execution_when_container_unavailable(self, tmp_path: Path) -> None:
        """When container sandbox is unavailable, runner preserves code and blocks grading."""
        code_completion = (
            "```python\n"
            "def send_with_retry(request, transport, policy, *, clock, sleep):\n"
            "    return transport.send(request)\n"
            "```"
        )
        provider = FakeMockProvider(response_text=code_completion)
        task_dir = BENCHMARK_TASKS_DIR / "T01_retry_semantics"

        # Mock ContainerExecutionBackend.is_available to return False
        with patch("atavism.execution.ContainerExecutionBackend.is_available", return_value=(False, "Docker daemon not running")):
            rec = run_single_trial(
                task_dir=task_dir,
                variant="A",
                provider=provider,
                model="meta-llama/llama-3.3-70b-instruct:free",
                output_base_dir=tmp_path,
                dry_run=False,
            )

        assert rec.trial_status == "SECURITY_BLOCKED"
        assert rec.failure_category == "CONTAINER_SANDBOX_UNAVAILABLE"
        assert "execution is blocked because OCI container isolation is unavailable" in rec.notes

        # Candidate file must be saved and preserved
        cand_files = list(tmp_path.rglob("candidate.py"))
        assert len(cand_files) == 1
        assert "def send_with_retry" in cand_files[0].read_text(encoding="utf-8")

        # Transcript must be saved
        transcripts = list(tmp_path.rglob("transcript.txt"))
        assert len(transcripts) == 1


class TestReportingAggregation:
    """Verify result aggregation and report formatting."""

    def test_aggregate_and_format_report(self, tmp_path: Path) -> None:
        # Create two sample trial records
        t1 = TrialRecord(
            trial_id="T01-A-test-trial01",
            timestamp="2026-11-06T12:00:00Z",
            task_id="T01_retry_semantics",
            variant="A",
            trial_status="COMPLETED",
            model={"name": "test-model:free"},
            grader_result={"passed": True, "total_tests": 47},
        )
        t2 = TrialRecord(
            trial_id="T01-B-test-trial01",
            timestamp="2026-11-06T12:05:00Z",
            task_id="T01_retry_semantics",
            variant="B",
            trial_status="COMPLETED",
            model={"name": "test-model:free"},
            grader_result={"passed": False, "total_tests": 50},
            failure_category="CONTRACT_REGRESSION",
        )

        dir1 = tmp_path / "t1"
        dir2 = tmp_path / "t2"
        t1.save(dir1)
        t2.save(dir2)

        records = find_trial_records(tmp_path)
        assert len(records) == 2

        aggregated = aggregate_evaluation_results(records)
        assert aggregated["total_records"] == 2
        assert "test-model:free" in aggregated["models"]
        model_stats = aggregated["models"]["test-model:free"]
        assert model_stats["completed_trials"] == 2
        assert model_stats["overall_pass_rate"] == 0.5

        t1_stats = model_stats["tasks"]["T01_retry_semantics"]
        assert t1_stats["variant_A"]["pass_rate"] == 1.0
        assert t1_stats["variant_B"]["pass_rate"] == 0.0
        assert t1_stats["delta"] == -1.0

        md = format_markdown_report(aggregated)
        assert "Atavism — Model Evaluation Summary Report" in md
        assert "test-model:free" in md
        assert "-100.0%" in md

