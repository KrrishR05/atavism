"""Reporting — aggregation and analysis of trial results.

Provides utilities for computing pass rates, pass@k, pass^k,
and comparing control vs. treatment performance.
Actual reporting is not exercised until model trials are run.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


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
    """Compute pass@k: probability at least 1 of k samples passes.

    Args:
        n: Total number of samples.
        c: Number of correct (passing) samples.
        k: Number of samples drawn.

    Returns:
        Estimated probability that at least one of k samples passes.
    """
    if n == 0 or k == 0:
        return 0.0
    if c == n:
        return 1.0
    if c == 0:
        return 0.0

    # pass@k = 1 - C(n-c, k) / C(n, k)
    # Use log-space to avoid overflow
    log_numerator = sum(math.log(n - c - i) for i in range(k) if n - c - i > 0)
    log_denominator = sum(math.log(n - i) for i in range(k))

    if k > n - c:
        return 1.0

    return 1.0 - math.exp(log_numerator - log_denominator)


def compute_pass_pow_k(pass_rate: float, k: int) -> float:
    """Compute pass^k: probability all k samples pass.

    Args:
        pass_rate: Single-trial pass probability.
        k: Number of samples.

    Returns:
        pass_rate ** k
    """
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

