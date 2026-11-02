"""Control-specific tests for T01 Variant A.

409 LEASE_BUSY is NOT retryable in the control variant.
"""

from __future__ import annotations

from atavism_retry.client import send_with_retry
from atavism_retry.types import RetryPolicy

from conftest import (
    DEFAULT_POLICY,
    FakeClock,
    FakeSleeper,
    FakeTransport,
    get_request,
    lease_busy,
    ok_response,
    post_request,
)


class TestControlLeasebusy:
    """409 LEASE_BUSY must NOT be retried in control variant A."""

    def test_409_lease_busy_not_retried(self) -> None:
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        transport = FakeTransport([lease_busy(), ok_response()])
        result = send_with_retry(get_request(), transport, DEFAULT_POLICY, clock=clock, sleep=sleep)
        assert result.status == 409
        assert transport.call_count == 1

    def test_409_lease_busy_returned_immediately(self) -> None:
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        transport = FakeTransport([lease_busy()])
        result = send_with_retry(get_request(), transport, DEFAULT_POLICY, clock=clock, sleep=sleep)
        assert result.status == 409
        assert result.error_code == "LEASE_BUSY"
        assert transport.call_count == 1
        assert sleep.sleep_calls == []

    def test_409_lease_busy_post_with_key_not_retried(self) -> None:
        """Even with idempotency key, 409 LEASE_BUSY is not retryable in control."""
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        transport = FakeTransport([lease_busy()])
        req = post_request(idempotency_key="key-123")
        result = send_with_retry(req, transport, DEFAULT_POLICY, clock=clock, sleep=sleep)
        assert result.status == 409
        assert transport.call_count == 1

