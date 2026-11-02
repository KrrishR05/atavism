"""Meridian Gateway retry client — implementation.

Implement the send_with_retry function according to the contract
specified in contract.md.
"""

from __future__ import annotations

from .types import Clock, Request, Response, RetryPolicy, Sleeper, Transport


def send_with_retry(
    request: Request,
    transport: Transport,
    policy: RetryPolicy,
    *,
    clock: Clock,
    sleep: Sleeper,
) -> Response:
    """Send a request with retry logic as specified by the Meridian Gateway contract.

    Args:
        request: The HTTP request to send.
        transport: Callable that sends the request and returns a response.
        policy: Retry policy configuration.
        clock: Monotonic clock function.
        sleep: Sleep function for delays.

    Returns:
        The final HTTP response after retries are exhausted or a
        non-retryable response is received.
    """
    raise NotImplementedError("Implement this function according to contract.md")

