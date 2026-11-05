"""Alternative valid reference implementation for T01 Control (Variant A).

Serves as a positive control to verify that graders do not overfit to the
primary reference implementation's internal coding style.
"""

from __future__ import annotations

import math

from atavism_retry.types import Clock, Request, Response, RetryPolicy, Sleeper, Transport

_RETRYABLE_STATUSES = {
    (429, "RATE_LIMITED"),
    (503, "TEMPORARY_UNAVAILABLE"),
}


def _should_retry_status(status: int, code: str) -> bool:
    return (status, code) in _RETRYABLE_STATUSES


def _is_safe_or_idempotent(request: Request) -> bool:
    method = request.method.upper()
    if method in {"GET", "HEAD", "OPTIONS"}:
        return True
    key = request.headers.get("Idempotency-Key")
    return bool(key and len(key) > 0)


def _calculate_backoff_delay(retry_count: int, base: float, cap: float) -> float:
    exp = retry_count - 1
    if exp <= 0:
        return min(base, cap)
    if base <= 0.0 or cap <= 0.0:
        return 0.0
    if base >= cap:
        return cap
    try:
        ratio = cap / base
        if ratio <= 0.0 or exp >= math.log2(ratio):
            return cap
        return min(base * (2.0 ** exp), cap)
    except (OverflowError, ValueError):
        return cap


def _extract_retry_after(headers: dict[str, str]) -> float | None:
    val = headers.get("Retry-After")
    if val is None:
        return None
    val_str = val.strip()
    if not val_str or not val_str.isdigit():
        return None
    # Reject leading signs or weird representations
    if str(int(val_str)) != val_str:
        return None
    seconds = int(val_str)
    return float(seconds) if seconds >= 0 else None


def send_with_retry(
    request: Request,
    transport: Transport,
    policy: RetryPolicy,
    *,
    clock: Clock,
    sleep: Sleeper,
) -> Response:
    """Alternative valid implementation using a while loop."""
    start_time = clock()
    deadline = start_time + policy.timeout

    attempts_made = 0
    latest_response: Response | None = None

    while attempts_made < policy.max_attempts:
        attempts_made += 1
        latest_response = transport(request)

        # Terminal conditions: exhausted attempts or non-retryable response
        if attempts_made >= policy.max_attempts:
            return latest_response

        if not _should_retry_status(latest_response.status, latest_response.error_code):
            return latest_response

        if not _is_safe_or_idempotent(request):
            return latest_response

        # Determine delay
        explicit_delay = _extract_retry_after(latest_response.headers)
        if explicit_delay is not None:
            delay = explicit_delay
        else:
            delay = _calculate_backoff_delay(attempts_made, policy.base_delay, policy.max_backoff)

        # Check deadline before sleeping
        current_time = clock()
        if current_time + delay >= deadline:
            return latest_response

        sleep(delay)

        # Re-check deadline after sleeping
        if clock() >= deadline:
            return latest_response

    assert latest_response is not None
    return latest_response

