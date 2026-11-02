"""Treatment-specific tests for T01 Variant B.

409 LEASE_BUSY IS retryable in the treatment variant.
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


class TestTreatmentLeasebusy:
    """409 LEASE_BUSY must be retried in treatment variant B."""

    def test_409_lease_busy_retried(self) -> None:
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        transport = FakeTransport([lease_busy(), ok_response()])
        result = send_with_retry(get_request(), transport, DEFAULT_POLICY, clock=clock, sleep=sleep)
        assert result.status == 200
        assert transport.call_count == 2

    def test_409_lease_busy_backoff_applied(self) -> None:
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        transport = FakeTransport([lease_busy(), lease_busy(), ok_response()])
        policy = RetryPolicy(max_attempts=5, base_delay=1.0, max_backoff=30.0, timeout=120.0)
        result = send_with_retry(get_request(), transport, policy, clock=clock, sleep=sleep)
        assert result.status == 200
        assert sleep.sleep_calls == [1.0, 2.0]

    def test_409_lease_busy_retry_after_respected(self) -> None:
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        transport = FakeTransport([lease_busy(retry_after="7"), ok_response()])
        result = send_with_retry(get_request(), transport, DEFAULT_POLICY, clock=clock, sleep=sleep)
        assert result.status == 200
        assert sleep.sleep_calls == [7.0]

    def test_409_lease_busy_post_with_key_retried(self) -> None:
        """POST with idempotency key can retry 409 LEASE_BUSY in treatment."""
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        transport = FakeTransport([lease_busy(), ok_response()])
        req = post_request(idempotency_key="key-456")
        result = send_with_retry(req, transport, DEFAULT_POLICY, clock=clock, sleep=sleep)
        assert result.status == 200
        assert transport.call_count == 2

    def test_409_lease_busy_post_without_key_not_retried(self) -> None:
        """POST without idempotency key cannot retry, even though 409 LEASE_BUSY is retryable."""
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        transport = FakeTransport([lease_busy()])
        req = post_request()
        result = send_with_retry(req, transport, DEFAULT_POLICY, clock=clock, sleep=sleep)
        assert result.status == 409
        assert transport.call_count == 1

    def test_409_lease_busy_exhausts_attempts(self) -> None:
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        policy = RetryPolicy(max_attempts=3, base_delay=1.0, max_backoff=30.0, timeout=120.0)
        transport = FakeTransport([lease_busy(), lease_busy(), lease_busy()])
        result = send_with_retry(get_request(), transport, policy, clock=clock, sleep=sleep)
        assert result.status == 409
        assert transport.call_count == 3

