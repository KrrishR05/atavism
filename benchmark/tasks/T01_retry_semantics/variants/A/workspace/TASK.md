# Task: Implement a Retry Client for Meridian Gateway

## Overview

You are implementing a retry-capable HTTP client for the **Meridian Gateway** API provider. Meridian Gateway is a synthetic API provider created for this evaluation.

Your implementation must follow the provider's retry contract exactly as specified in `contract.md`.

## What to Implement

Complete the `send_with_retry` function in `src/atavism_retry/client.py`.

The function signature is:

```python
def send_with_retry(
    request: Request,
    transport: Transport,
    policy: RetryPolicy,
    *,
    clock: Clock,
    sleep: Sleeper,
) -> Response:
    ...
```

All types are defined in `src/atavism_retry/types.py`. Do not modify the type definitions.

## Requirements Summary

Read `contract.md` for the complete specification. Key requirements:

1. **Retry only explicitly retryable combinations** as defined in the contract.
2. **Exponential backoff** with the formula: `min(base_delay * 2 ** (retry_number - 1), max_backoff)`.
3. **Retry-After header support** for non-negative integer seconds.
4. **Deadline enforcement** using the injected monotonic clock.
5. **Idempotency enforcement** for non-safe HTTP methods.
6. **No real I/O** — use only the injected transport, clock, and sleeper.

## Files

- `src/atavism_retry/types.py` — Type definitions (do not modify).
- `src/atavism_retry/client.py` — Implement `send_with_retry` here.
- `contract.md` — The Meridian Gateway retry contract.

## Deliverable

A complete implementation of `send_with_retry` in `client.py` that passes all contract requirements.

