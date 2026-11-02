"""Trial recording — data structures for evaluation trial records.

Provides the schema and utilities for recording individual model trials.
Actual model invocation is not implemented in this initial phase.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class TrialRecord:
    """Record of a single model evaluation trial."""
    task_id: str
    variant: str
    model_name: str
    model_version: str
    model_settings: dict[str, object] = field(default_factory=dict)
    trial_number: int = 1
    python_version: str = ""
    dependencies: dict[str, str] = field(default_factory=dict)
    started_at: str = ""
    completed_at: str = ""
    duration_seconds: float = 0.0
    approximate_cost_usd: float | None = None
    candidate_path: str = ""
    transcript_path: str = ""
    grader_passed: bool = False
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    failure_details: list[str] = field(default_factory=list)
    failure_category: str = ""
    notes: str = ""

    def save(self, output_dir: Path) -> Path:
        """Save this trial record as JSON."""
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"trial_{self.task_id}_{self.variant}_{self.model_name}_{self.trial_number}.json"
        path = output_dir / filename
        with open(path, "w") as f:
            json.dump(asdict(self), f, indent=2, default=str)
        return path

    @classmethod
    def load(cls, path: Path) -> TrialRecord:
        """Load a trial record from JSON."""
        with open(path) as f:
            data = json.load(f)
        return cls(**data)

