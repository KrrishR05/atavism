"""Reference implementation for T01 Control (Variant A).

409 LEASE_BUSY is NOT retryable in this variant.
Retryable: (429, RATE_LIMITED), (503, TEMPORARY_UNAVAILABLE).
"""

from __future__ import annotations

import math

from atavism_retry.types import Clock, Request, Response, RetryPolicy, Sleeper, Transport

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

_RETRYABLE = frozenset({
    (429, "RATE_LIMITED"),
    (503, "TEMPORARY_UNAVAILABLE"),
})


def _is_retryable(response: Response) -> bool:
    return (response.status, response.error_code) in _RETRYABLE


def _is_replayable(request: Request) -> bool:
    if request.method.upper() in _SAFE_METHODS:
        return True
    key = request.headers.get("Idempotency-Key", "")
    return len(key) > 0


def _compute_backoff(retry_number: int, policy: RetryPolicy) -> float:
    exp = retry_number - 1
    if exp <= 0:
        return min(policy.base_delay, policy.max_backoff)
    if policy.base_delay <= 0.0 or policy.max_backoff <= 0.0:
        return 0.0
    if policy.base_delay >= policy.max_backoff:
        return policy.max_backoff
    try:
        ratio = policy.max_backoff / policy.base_delay
        if ratio <= 0.0:
            return policy.max_backoff
        max_exp = math.log2(ratio)
        if exp >= max_exp:
            return policy.max_backoff
        return min(policy.base_delay * (2.0 ** exp), policy.max_backoff)
    except (OverflowError, ValueError):
        return policy.max_backoff

def _parse_retry_after(response: Response) -> float | None:
    raw = response.headers.get("Retry-After")
    if raw is None:
        return None
    stripped = raw.strip()
    if not stripped:
        return None
    try:
        value = int(stripped)
    except ValueError:
        return None
    # Must be exact integer representation (reject "1.0", "1e2", etc.)
    if stripped != str(value):
        return None
    if value < 0:
        return None
    return float(value)


def send_with_retry(
    request: Request,
    transport: Transport,
    policy: RetryPolicy,
    *,
    clock: Clock,
    sleep: Sleeper,
) -> Response:
    """Send request with retry logic — Control variant (A)."""
    deadline = clock() + policy.timeout
    response: Response | None = None

    for attempt in range(1, policy.max_attempts + 1):
        response = transport(request)

        # Last attempt — return regardless.
        if attempt >= policy.max_attempts:
            return response

        # Non-retryable response — return immediately.
        if not _is_retryable(response):
            return response

        # Retryable but not replayable — return immediately.
        if not _is_replayable(request):
            return response

        # Compute delay.
        retry_number = attempt  # retry_number = 1 for first retry
        retry_after = _parse_retry_after(response)
        if retry_after is not None:
            delay = retry_after
        else:
            delay = _compute_backoff(retry_number, policy)

        # Deadline check before sleeping.
        now = clock()
        if now + delay >= deadline:
            return response

        sleep(delay)

        # Deadline check after sleeping.
        if clock() >= deadline:
            return response

    # Should not reach here if max_attempts >= 1, but safety return.
    assert response is not None
    return response

