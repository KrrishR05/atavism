"""Mutation fixtures — deliberately incorrect implementations.

Each mutant introduces a specific, common error to validate that the grader
catches it. Named by the defect they embody.
"""

from __future__ import annotations

import math

from atavism_retry.types import Clock, Request, Response, RetryPolicy, Sleeper, Transport

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def _compute_backoff_safe(retry_number: int, policy: RetryPolicy) -> float:
    exp = retry_number - 1
    if exp <= 0:
        return min(policy.base_delay, policy.max_backoff)
    if policy.base_delay <= 0.0 or policy.max_backoff <= 0.0:
        return 0.0
    if policy.base_delay >= policy.max_backoff:
        return policy.max_backoff
    try:
        ratio = policy.max_backoff / policy.base_delay
        if ratio <= 0.0 or exp >= math.log2(ratio):
            return policy.max_backoff
        return min(policy.base_delay * (2.0 ** exp), policy.max_backoff)
    except (OverflowError, ValueError):
        return policy.max_backoff


def _parse_retry_after_safe(response: Response) -> float | None:
    raw = response.headers.get("Retry-After")
    if raw is None:
        return None
    stripped = raw.strip()
    if not stripped or not stripped.isdigit() or str(int(stripped)) != stripped:
        return None
    val = int(stripped)
    return float(val) if val >= 0 else None


# ---------------------------------------------------------------------------
# Mutant 1: retry_all_errors
# Retries every 4xx/5xx regardless of status/error-code combination.
# ---------------------------------------------------------------------------

def mutant_retry_all_errors(
    request: Request,
    transport: Transport,
    policy: RetryPolicy,
    *,
    clock: Clock,
    sleep: Sleeper,
) -> Response:
    """DEFECT: Retries all 4xx and 5xx responses."""
    deadline = clock() + policy.timeout
    response: Response | None = None

    for attempt in range(1, policy.max_attempts + 1):
        response = transport(request)

        if attempt >= policy.max_attempts:
            return response

        # DEFECT: retries any 4xx or 5xx
        if response.status < 400:
            return response

        if request.method.upper() not in _SAFE_METHODS:
            if not request.headers.get("Idempotency-Key", ""):
                return response

        retry_number = attempt
        ra = _parse_retry_after_safe(response)
        delay = ra if ra is not None else _compute_backoff_safe(retry_number, policy)

        now = clock()
        if now + delay >= deadline:
            return response

        sleep(delay)
        if clock() >= deadline:
            return response

    assert response is not None
    return response


# ---------------------------------------------------------------------------
# Mutant 2: ignore_error_code
# Only checks HTTP status, ignores the error_code field.
# ---------------------------------------------------------------------------

def mutant_ignore_error_code(
    request: Request,
    transport: Transport,
    policy: RetryPolicy,
    *,
    clock: Clock,
    sleep: Sleeper,
) -> Response:
    """DEFECT: Retries 429 and 503 regardless of error_code."""
    deadline = clock() + policy.timeout
    response: Response | None = None

    for attempt in range(1, policy.max_attempts + 1):
        response = transport(request)

        if attempt >= policy.max_attempts:
            return response

        # DEFECT: ignores error_code
        if response.status not in (429, 503):
            return response

        if request.method.upper() not in _SAFE_METHODS:
            if not request.headers.get("Idempotency-Key", ""):
                return response

        retry_number = attempt
        ra = _parse_retry_after_safe(response)
        delay = ra if ra is not None else _compute_backoff_safe(retry_number, policy)

        now = clock()
        if now + delay >= deadline:
            return response

        sleep(delay)
        if clock() >= deadline:
            return response

    assert response is not None
    return response


# ---------------------------------------------------------------------------
# Mutant 3: off_by_one_attempts
# Treats max_attempts as retry count (not total attempts).
# ---------------------------------------------------------------------------

def mutant_off_by_one_attempts(
    request: Request,
    transport: Transport,
    policy: RetryPolicy,
    *,
    clock: Clock,
    sleep: Sleeper,
) -> Response:
    """DEFECT: max_attempts treated as max retries, not max total attempts."""
    _retryable = frozenset({(429, "RATE_LIMITED"), (503, "TEMPORARY_UNAVAILABLE")})
    deadline = clock() + policy.timeout
    response: Response | None = None

    # DEFECT: allows max_attempts retries PLUS the initial attempt
    for attempt in range(0, policy.max_attempts + 1):
        response = transport(request)

        if attempt >= policy.max_attempts:
            return response

        if (response.status, response.error_code) not in _retryable:
            return response

        if request.method.upper() not in _SAFE_METHODS:
            if not request.headers.get("Idempotency-Key", ""):
                return response

        retry_number = attempt + 1
        delay = _compute_backoff_safe(retry_number, policy)

        now = clock()
        if now + delay >= deadline:
            return response

        sleep(delay)
        if clock() >= deadline:
            return response

    assert response is not None
    return response


# ---------------------------------------------------------------------------
# Mutant 4: ignore_retry_after
# Ignores Retry-After header entirely.
# ---------------------------------------------------------------------------

def mutant_ignore_retry_after(
    request: Request,
    transport: Transport,
    policy: RetryPolicy,
    *,
    clock: Clock,
    sleep: Sleeper,
) -> Response:
    """DEFECT: Ignores Retry-After header, always uses exponential backoff."""
    _retryable = frozenset({(429, "RATE_LIMITED"), (503, "TEMPORARY_UNAVAILABLE")})
    deadline = clock() + policy.timeout
    response: Response | None = None

    for attempt in range(1, policy.max_attempts + 1):
        response = transport(request)

        if attempt >= policy.max_attempts:
            return response

        if (response.status, response.error_code) not in _retryable:
            return response

        if request.method.upper() not in _SAFE_METHODS:
            if not request.headers.get("Idempotency-Key", ""):
                return response

        retry_number = attempt
        # DEFECT: always uses backoff, never checks Retry-After
        delay = _compute_backoff_safe(retry_number, policy)

        now = clock()
        if now + delay >= deadline:
            return response

        sleep(delay)
        if clock() >= deadline:
            return response

    assert response is not None
    return response


# ---------------------------------------------------------------------------
# Mutant 5: wrong_backoff_formula
# Uses retry_number instead of (retry_number - 1) as exponent.
# ---------------------------------------------------------------------------

def mutant_wrong_backoff(
    request: Request,
    transport: Transport,
    policy: RetryPolicy,
    *,
    clock: Clock,
    sleep: Sleeper,
) -> Response:
    """DEFECT: Uses 2^retry_number instead of 2^(retry_number-1)."""
    _retryable = frozenset({(429, "RATE_LIMITED"), (503, "TEMPORARY_UNAVAILABLE")})
    deadline = clock() + policy.timeout
    response: Response | None = None

    for attempt in range(1, policy.max_attempts + 1):
        response = transport(request)

        if attempt >= policy.max_attempts:
            return response

        if (response.status, response.error_code) not in _retryable:
            return response

        if request.method.upper() not in _SAFE_METHODS:
            if not request.headers.get("Idempotency-Key", ""):
                return response

        retry_number = attempt
        # DEFECT: wrong exponent (uses retry_number instead of retry_number - 1)
        try:
            ratio = policy.max_backoff / policy.base_delay if policy.base_delay > 0 else 0.0
            if ratio > 0 and retry_number >= math.log2(ratio):
                delay = policy.max_backoff
            else:
                delay = min(policy.base_delay * (2.0 ** retry_number), policy.max_backoff)
        except (OverflowError, ValueError):
            delay = policy.max_backoff

        now = clock()
        if now + delay >= deadline:
            return response

        sleep(delay)
        if clock() >= deadline:
            return response

    assert response is not None
    return response


# ---------------------------------------------------------------------------
# Mutant 6: retry_without_idempotency
# Retries unsafe methods even without Idempotency-Key.
# ---------------------------------------------------------------------------

def mutant_no_idempotency_check(
    request: Request,
    transport: Transport,
    policy: RetryPolicy,
    *,
    clock: Clock,
    sleep: Sleeper,
) -> Response:
    """DEFECT: Skips idempotency check, retries all methods."""
    _retryable = frozenset({(429, "RATE_LIMITED"), (503, "TEMPORARY_UNAVAILABLE")})
    deadline = clock() + policy.timeout
    response: Response | None = None

    for attempt in range(1, policy.max_attempts + 1):
        response = transport(request)

        if attempt >= policy.max_attempts:
            return response

        if (response.status, response.error_code) not in _retryable:
            return response

        # DEFECT: no idempotency check

        retry_number = attempt
        ra = _parse_retry_after_safe(response)
        delay = ra if ra is not None else _compute_backoff_safe(retry_number, policy)

        now = clock()
        if now + delay >= deadline:
            return response

        sleep(delay)
        if clock() >= deadline:
            return response

    assert response is not None
    return response


# ---------------------------------------------------------------------------
# Mutant 7: ignore_deadline
# Never checks the deadline.
# ---------------------------------------------------------------------------

def mutant_ignore_deadline(
    request: Request,
    transport: Transport,
    policy: RetryPolicy,
    *,
    clock: Clock,
    sleep: Sleeper,
) -> Response:
    """DEFECT: Ignores the deadline entirely."""
    _retryable = frozenset({(429, "RATE_LIMITED"), (503, "TEMPORARY_UNAVAILABLE")})
    response: Response | None = None

    for attempt in range(1, policy.max_attempts + 1):
        response = transport(request)

        if attempt >= policy.max_attempts:
            return response

        if (response.status, response.error_code) not in _retryable:
            return response

        if request.method.upper() not in _SAFE_METHODS:
            if not request.headers.get("Idempotency-Key", ""):
                return response

        retry_number = attempt
        ra = _parse_retry_after_safe(response)
        delay = ra if ra is not None else _compute_backoff_safe(retry_number, policy)

        # DEFECT: no deadline check
        sleep(delay)

    assert response is not None
    return response


# ---------------------------------------------------------------------------
# Mutant 8: swallow_exceptions
# Catches transport exceptions and returns a synthetic error response.
# ---------------------------------------------------------------------------

def mutant_swallow_exceptions(
    request: Request,
    transport: Transport,
    policy: RetryPolicy,
    *,
    clock: Clock,
    sleep: Sleeper,
) -> Response:
    """DEFECT: Catches transport exceptions instead of propagating them."""
    _retryable = frozenset({(429, "RATE_LIMITED"), (503, "TEMPORARY_UNAVAILABLE")})
    deadline = clock() + policy.timeout
    response: Response | None = None

    for attempt in range(1, policy.max_attempts + 1):
        try:
            response = transport(request)
        except Exception:
            # DEFECT: swallows exceptions
            return Response(status=500, error_code="TRANSPORT_ERROR", body=b"Transport failed")

        if attempt >= policy.max_attempts:
            return response

        if (response.status, response.error_code) not in _retryable:
            return response

        if request.method.upper() not in _SAFE_METHODS:
            if not request.headers.get("Idempotency-Key", ""):
                return response

        retry_number = attempt
        ra = _parse_retry_after_safe(response)
        delay = ra if ra is not None else _compute_backoff_safe(retry_number, policy)

        now = clock()
        if now + delay >= deadline:
            return response

        sleep(delay)
        if clock() >= deadline:
            return response

    assert response is not None
    return response


# ---------------------------------------------------------------------------
# Mutant 9: treatment_as_control (uses control behavior for treatment)
# This is the key cross-contamination mutant.
# ---------------------------------------------------------------------------

def mutant_treatment_as_control(
    request: Request,
    transport: Transport,
    policy: RetryPolicy,
    *,
    clock: Clock,
    sleep: Sleeper,
) -> Response:
    """DEFECT: Uses control retry set (no 409 LEASE_BUSY) in treatment context.

    This mutant is correct for variant A but WRONG for variant B.
    """
    # Control retryable set — missing (409, LEASE_BUSY)
    _retryable = frozenset({(429, "RATE_LIMITED"), (503, "TEMPORARY_UNAVAILABLE")})
    deadline = clock() + policy.timeout
    response: Response | None = None

    for attempt in range(1, policy.max_attempts + 1):
        response = transport(request)

        if attempt >= policy.max_attempts:
            return response

        if (response.status, response.error_code) not in _retryable:
            return response

        if request.method.upper() not in _SAFE_METHODS:
            if not request.headers.get("Idempotency-Key", ""):
                return response

        retry_number = attempt
        retry_after_raw = response.headers.get("Retry-After")
        delay: float | None = None
        if retry_after_raw is not None:
            stripped = retry_after_raw.strip()
            if stripped:
                try:
                    val = int(stripped)
                    if stripped == str(val) and val >= 0:
                        delay = float(val)
                except ValueError:
                    pass
        if delay is None:
            delay = _compute_backoff_safe(retry_number, policy)

        now = clock()
        if now + delay >= deadline:
            return response

        sleep(delay)
        if clock() >= deadline:
            return response

    assert response is not None
    return response

