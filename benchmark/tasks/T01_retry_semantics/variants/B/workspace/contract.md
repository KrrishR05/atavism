# Meridian Gateway — Retry Contract v2.4

*This document is the authoritative specification for retry behavior when interacting with the Meridian Gateway API.*

## 1. Retryable Responses

A response is retryable **only** if it matches one of the following combinations:

| HTTP Status | Error Code           | Retryable |
|-------------|----------------------|-----------|
| 429         | RATE_LIMITED         | Yes       |
| 503         | TEMPORARY_UNAVAILABLE| Yes       |
| 409         | LEASE_BUSY           | Yes       |

All other HTTP status and error-code combinations are **not retryable**, including but not limited to:

- 409 with an error code other than LEASE_BUSY.
- 429 or 503 with an error code not listed above.
- Any 4xx or 5xx status not listed above.

If a response is not retryable, return it immediately.

## 2. Attempt Counting

- `max_attempts` in the retry policy includes the initial request.
- `max_attempts = 1` means no retries (only the initial attempt).
- `max_attempts` must be at least 1.
- When all attempts are exhausted, return the most recent response.

## 3. Exponential Backoff

Calculate the delay before each retry using:

```
delay = min(base_delay * 2 ** (retry_number - 1), max_backoff)
```

Where:
- `base_delay` is `policy.base_delay` (in seconds).
- `max_backoff` is `policy.max_backoff` (in seconds).
- `retry_number` starts at 1 for the first retry (the second overall attempt).

No random jitter is applied.

Guard against arithmetic overflow by applying the `min()` cap before any intermediate value can overflow.

## 4. Retry-After Header

If a retryable response includes a `Retry-After` header:

1. Parse it as a non-negative integer representing seconds.
2. If valid, use this value as the delay instead of the exponential backoff calculation.
3. A valid `Retry-After` delay is **not** capped by `max_backoff`.
4. A valid `Retry-After` delay **must** still respect the overall deadline.
5. If the value is not a valid non-negative integer (negative, non-numeric, floating-point, empty, or an HTTP-date), ignore it and fall back to exponential backoff.

Do not parse HTTP-date formatted `Retry-After` values.

## 5. Deadline

- Establish a deadline at function entry: `deadline = clock() + policy.timeout`.
- Before sleeping, check: if `clock() + delay >= deadline`, do not retry. Return the most recent response.
- After sleeping, recheck: if `clock() >= deadline`, do not retry. Return the most recent response.
- Do not attempt to cancel a transport call already in progress.
- If the retry budget (attempts or deadline) is exhausted, return the most recent response.

## 6. Idempotency

- The HTTP methods GET, HEAD, and OPTIONS are automatically safe for replay.
- For all other methods (POST, PUT, DELETE, PATCH, etc.), the request must include a non-empty `Idempotency-Key` header to be eligible for retry.
- If a non-safe method lacks an `Idempotency-Key` (or has an empty one), do not retry — return the response immediately, even if it is otherwise retryable.
- Preserve the same `Idempotency-Key` across all retry attempts.
- Do not generate, modify, or remove idempotency keys.
- Do not mutate the original request object.

## 7. Exception Handling

- If the transport raises an exception, propagate it unchanged to the caller.
- Do not catch and retry transport exceptions.
- Do not wrap, suppress, or replace exceptions.

## 8. Determinism

This client must operate deterministically:

- Use only the injected `transport` for HTTP calls.
- Use only the injected `clock` for time readings.
- Use only the injected `sleep` for delays.
- Do not make real network calls, use real timers, or read system clocks.

