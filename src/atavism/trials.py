"""Trial recording — data structures and persistence for evaluation trial records.

Conforms to the provenance schema in docs/evaluation_protocol.md.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class TrialModelInfo:
    """Model configuration and metadata for a trial."""
    provider: str
    name: str
    actual_returned_name: str = ""
    temperature: float = 0.0
    max_tokens: int = 4096
    pricing_tier: str = "FREE"


@dataclass
class TrialGraderResult:
    """Grader results for a trial."""
    passed: bool = False
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    errors: int = 0
    diagnostics: dict[str, float] = field(default_factory=dict)
    failure_reasons: list[str] = field(default_factory=list)


@dataclass
class TrialExecutionMetrics:
    """Execution performance and resource metrics."""
    duration_seconds: float = 0.0
    latency_seconds: float = 0.0
    tokens_prompt: int | None = None
    tokens_completion: int | None = None
    tokens_total: int | None = None
    cost_usd: float | None = 0.0


@dataclass
class TrialRecord:
    """Structured record of an individual model evaluation trial."""
    trial_id: str
    timestamp: str
    task_id: str
    variant: str
    benchmark_commit: str = ""
    grader_version: str = "1.0.0"
    execution_backend: str = "container_docker"
    trust_level: str = "untrusted"
    trial_status: str = "PENDING"  # COMPLETED, SECURITY_BLOCKED, SYNTAX_ERROR, ERROR, DRY_RUN
    model: dict[str, Any] = field(default_factory=dict)
    candidate_code_hash: str = ""
    manifest_hashes: dict[str, str] = field(default_factory=dict)
    grader_result: dict[str, Any] | None = None
    execution_metrics: dict[str, Any] = field(default_factory=dict)
    failure_category: str | None = None
    notes: str = ""

    def save(self, output_dir: Path) -> Path:
        """Save this trial record as metadata.json inside the trial directory."""
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "metadata.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2, default=str)
        return path

    @classmethod
    def load(cls, path: Path) -> TrialRecord:
        """Load a trial record from JSON."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)
