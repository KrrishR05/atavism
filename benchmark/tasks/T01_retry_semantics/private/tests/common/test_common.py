"""Common tests for T01 — shared across control and treatment variants.

These tests verify behavior that must be identical in both variants:
- 429/RATE_LIMITED retryable
- 503/TEMPORARY_UNAVAILABLE retryable
- Non-retryable responses returned immediately
- Exponential backoff
- Retry-After header handling
- Deadline enforcement
- Attempt counting
- Idempotency enforcement
- Exception propagation
"""

from __future__ import annotations

import math
import pytest

from atavism_retry.types import Request, Response, RetryPolicy

# conftest.py provides: FakeTransport, FakeClock, FakeSleeper, helpers
from conftest import (
    DEFAULT_POLICY,
    FakeClock,
    FakeSleeper,
    FakeTransport,
    RaisingTransport,
    bad_request,
    conflict_other,
    get_request,
    head_request,
    internal_error,
    ok_response,
    options_request,
    post_request,
    rate_limited,
    temporarily_unavailable,
)

# The send_with_retry function is imported by the variant-specific conftest
# or test runner which sets up sys.path appropriately.
from atavism_retry.client import send_with_retry


# ===================================================================
# Retry classification — shared retryable codes
# ===================================================================

class TestRetryClassificationShared:
    """429/RATE_LIMITED and 503/TEMPORARY_UNAVAILABLE are retryable in both variants."""

    def test_429_rate_limited_retried(self) -> None:
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        transport = FakeTransport([rate_limited(), ok_response()])
        result = send_with_retry(get_request(), transport, DEFAULT_POLICY, clock=clock, sleep=sleep)
        assert result.status == 200
        assert transport.call_count == 2

    def test_503_temporary_unavailable_retried(self) -> None:
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        transport = FakeTransport([temporarily_unavailable(), ok_response()])
        result = send_with_retry(get_request(), transport, DEFAULT_POLICY, clock=clock, sleep=sleep)
        assert result.status == 200
        assert transport.call_count == 2


# ===================================================================
# Non-retryable responses
# ===================================================================

class TestNonRetryable:
    """Responses not in the retryable set must be returned immediately."""

    def test_200_returned_immediately(self) -> None:
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        transport = FakeTransport([ok_response()])
        result = send_with_retry(get_request(), transport, DEFAULT_POLICY, clock=clock, sleep=sleep)
        assert result.status == 200
        assert transport.call_count == 1

    def test_400_not_retried(self) -> None:
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        transport = FakeTransport([bad_request()])
        result = send_with_retry(get_request(), transport, DEFAULT_POLICY, clock=clock, sleep=sleep)
        assert result.status == 400
        assert transport.call_count == 1

    def test_500_internal_error_not_retried(self) -> None:
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        transport = FakeTransport([internal_error()])
        result = send_with_retry(get_request(), transport, DEFAULT_POLICY, clock=clock, sleep=sleep)
        assert result.status == 500
        assert transport.call_count == 1

    def test_409_other_conflict_not_retried(self) -> None:
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        transport = FakeTransport([conflict_other()])
        result = send_with_retry(get_request(), transport, DEFAULT_POLICY, clock=clock, sleep=sleep)
        assert result.status == 409
        assert transport.call_count == 1

    def test_429_wrong_error_code_not_retried(self) -> None:
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        resp = Response(status=429, error_code="UNKNOWN_CODE")
        transport = FakeTransport([resp])
        result = send_with_retry(get_request(), transport, DEFAULT_POLICY, clock=clock, sleep=sleep)
        assert result.status == 429
        assert transport.call_count == 1

    def test_503_wrong_error_code_not_retried(self) -> None:
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        resp = Response(status=503, error_code="WRONG_CODE")
        transport = FakeTransport([resp])
        result = send_with_retry(get_request(), transport, DEFAULT_POLICY, clock=clock, sleep=sleep)
        assert result.status == 503
        assert transport.call_count == 1


# ===================================================================
# Attempt counting
# ===================================================================

class TestAttemptCounting:
    """max_attempts includes the initial request."""

    def test_max_attempts_1_no_retry(self) -> None:
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        policy = RetryPolicy(max_attempts=1, base_delay=1.0, max_backoff=30.0, timeout=120.0)
        transport = FakeTransport([rate_limited()])
        result = send_with_retry(get_request(), transport, policy, clock=clock, sleep=sleep)
        assert result.status == 429
        assert transport.call_count == 1

    def test_max_attempts_3_makes_3_calls(self) -> None:
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        policy = RetryPolicy(max_attempts=3, base_delay=1.0, max_backoff=30.0, timeout=120.0)
        transport = FakeTransport([rate_limited(), rate_limited(), rate_limited()])
        result = send_with_retry(get_request(), transport, policy, clock=clock, sleep=sleep)
        assert result.status == 429
        assert transport.call_count == 3

    def test_returns_last_response_on_exhaustion(self) -> None:
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        policy = RetryPolicy(max_attempts=2, base_delay=1.0, max_backoff=30.0, timeout=120.0)
        final = rate_limited()
        transport = FakeTransport([rate_limited(), Response(status=429, error_code="RATE_LIMITED", body=b"final")])
        result = send_with_retry(get_request(), transport, policy, clock=clock, sleep=sleep)
        assert result.body == b"final"
        assert transport.call_count == 2

    def test_early_success_stops_retrying(self) -> None:
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        policy = RetryPolicy(max_attempts=5, base_delay=1.0, max_backoff=30.0, timeout=120.0)
        transport = FakeTransport([rate_limited(), ok_response()])
        result = send_with_retry(get_request(), transport, policy, clock=clock, sleep=sleep)
        assert result.status == 200
        assert transport.call_count == 2


# ===================================================================
# Exponential backoff
# ===================================================================

class TestExponentialBackoff:
    """Backoff: min(base_delay * 2^(retry_number-1), max_backoff), no jitter."""

    def test_backoff_sequence(self) -> None:
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        policy = RetryPolicy(max_attempts=5, base_delay=1.0, max_backoff=30.0, timeout=120.0)
        transport = FakeTransport([
            rate_limited(), rate_limited(), rate_limited(), rate_limited(), ok_response(),
        ])
        send_with_retry(get_request(), transport, policy, clock=clock, sleep=sleep)
        # retry_number: 1->1s, 2->2s, 3->4s, 4->8s
        assert sleep.sleep_calls == [1.0, 2.0, 4.0, 8.0]

    def test_backoff_capped_by_max(self) -> None:
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        policy = RetryPolicy(max_attempts=5, base_delay=2.0, max_backoff=5.0, timeout=120.0)
        transport = FakeTransport([
            rate_limited(), rate_limited(), rate_limited(), rate_limited(), ok_response(),
        ])
        send_with_retry(get_request(), transport, policy, clock=clock, sleep=sleep)
        # retry_number: 1->2s, 2->4s, 3->min(8,5)=5s, 4->min(16,5)=5s
        assert sleep.sleep_calls == [2.0, 4.0, 5.0, 5.0]

    def test_no_jitter(self) -> None:
        """Running the same scenario twice produces identical sleep durations."""
        results = []
        for _ in range(2):
            clock = FakeClock()
            sleep = FakeSleeper(clock)
            policy = RetryPolicy(max_attempts=4, base_delay=1.0, max_backoff=30.0, timeout=120.0)
            transport = FakeTransport([rate_limited(), rate_limited(), rate_limited(), ok_response()])
            send_with_retry(get_request(), transport, policy, clock=clock, sleep=sleep)
            results.append(sleep.sleep_calls)
        assert results[0] == results[1]

    def test_backoff_extreme_subnormal_base_delay(self) -> None:
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        policy = RetryPolicy(max_attempts=1050, base_delay=1e-320, max_backoff=1e-10, timeout=1e10)
        transport = FakeTransport([rate_limited() for _ in range(1049)] + [ok_response()])
        result = send_with_retry(get_request(), transport, policy, clock=clock, sleep=sleep)
        assert result.status == 200
        assert sleep.sleep_calls[-1] == 1e-10

    def test_backoff_extreme_large_values(self) -> None:
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        policy = RetryPolicy(max_attempts=10, base_delay=1e300, max_backoff=1e308, timeout=1e310)
        transport = FakeTransport([rate_limited() for _ in range(5)] + [ok_response()])
        result = send_with_retry(get_request(), transport, policy, clock=clock, sleep=sleep)
        assert result.status == 200
        assert math.isfinite(sleep.sleep_calls[0])

    def test_large_retry_number_no_overflow(self) -> None:
        """Backoff with extreme policy does not raise OverflowError."""
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        policy = RetryPolicy(max_attempts=100, base_delay=1.0, max_backoff=60.0, timeout=100000.0)
        responses = [rate_limited() for _ in range(99)] + [ok_response()]
        transport = FakeTransport(responses)
        result = send_with_retry(get_request(), transport, policy, clock=clock, sleep=sleep)
        assert result.status == 200
        # All sleeps should be capped at max_backoff, no infinities
        for s in sleep.sleep_calls:
            assert math.isfinite(s)
            assert s <= 60.0


# ===================================================================
# Retry-After header
# ===================================================================

class TestRetryAfterHeader:
    """Retry-After takes precedence when valid."""

    def test_retry_after_integer(self) -> None:
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        transport = FakeTransport([rate_limited(retry_after="5"), ok_response()])
        result = send_with_retry(get_request(), transport, DEFAULT_POLICY, clock=clock, sleep=sleep)
        assert result.status == 200
        assert sleep.sleep_calls == [5.0]

    def test_retry_after_zero(self) -> None:
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        transport = FakeTransport([rate_limited(retry_after="0"), ok_response()])
        result = send_with_retry(get_request(), transport, DEFAULT_POLICY, clock=clock, sleep=sleep)
        assert result.status == 200
        assert sleep.sleep_calls == [0.0]

    def test_retry_after_not_capped_by_max_backoff(self) -> None:
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        policy = RetryPolicy(max_attempts=3, base_delay=1.0, max_backoff=5.0, timeout=120.0)
        transport = FakeTransport([rate_limited(retry_after="60"), ok_response()])
        result = send_with_retry(get_request(), transport, policy, clock=clock, sleep=sleep)
        assert result.status == 200
        assert sleep.sleep_calls == [60.0]

    def test_retry_after_negative_ignored(self) -> None:
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        transport = FakeTransport([rate_limited(retry_after="-1"), ok_response()])
        result = send_with_retry(get_request(), transport, DEFAULT_POLICY, clock=clock, sleep=sleep)
        assert result.status == 200
        # Should fall back to exponential: 1.0
        assert sleep.sleep_calls == [1.0]

    def test_retry_after_float_ignored(self) -> None:
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        transport = FakeTransport([rate_limited(retry_after="1.5"), ok_response()])
        result = send_with_retry(get_request(), transport, DEFAULT_POLICY, clock=clock, sleep=sleep)
        assert result.status == 200
        assert sleep.sleep_calls == [1.0]

    def test_retry_after_non_numeric_ignored(self) -> None:
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        transport = FakeTransport([rate_limited(retry_after="Thu, 01 Jan 2099 00:00:00 GMT"), ok_response()])
        result = send_with_retry(get_request(), transport, DEFAULT_POLICY, clock=clock, sleep=sleep)
        assert result.status == 200
        assert sleep.sleep_calls == [1.0]

    def test_retry_after_empty_ignored(self) -> None:
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        transport = FakeTransport([rate_limited(retry_after=""), ok_response()])
        result = send_with_retry(get_request(), transport, DEFAULT_POLICY, clock=clock, sleep=sleep)
        assert result.status == 200
        assert sleep.sleep_calls == [1.0]

    def test_retry_after_respects_deadline(self) -> None:
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        policy = RetryPolicy(max_attempts=3, base_delay=1.0, max_backoff=30.0, timeout=10.0)
        transport = FakeTransport([rate_limited(retry_after="15")])
        result = send_with_retry(get_request(), transport, policy, clock=clock, sleep=sleep)
        # Retry-After of 15 exceeds the 10s timeout — should not retry
        assert result.status == 429
        assert transport.call_count == 1
        assert sleep.sleep_calls == []


# ===================================================================
# Deadline enforcement
# ===================================================================

class TestDeadline:
    """Deadline prevents retries that would exceed the timeout."""

    def test_no_retry_when_delay_exceeds_remaining(self) -> None:
        clock = FakeClock(start=0.0)
        sleep = FakeSleeper(clock)
        policy = RetryPolicy(max_attempts=5, base_delay=10.0, max_backoff=30.0, timeout=5.0)
        transport = FakeTransport([rate_limited()])
        result = send_with_retry(get_request(), transport, policy, clock=clock, sleep=sleep)
        # base_delay=10 > remaining=5 → no retry
        assert result.status == 429
        assert transport.call_count == 1

    def test_deadline_checked_after_sleep(self) -> None:
        """If clock has advanced past deadline after sleeping, stop."""
        clock = FakeClock(start=0.0)

        sleeps_done: list[float] = []

        def custom_sleep(seconds: float) -> None:
            sleeps_done.append(seconds)
            # Simulate time passing more than expected
            clock.advance(seconds + 100.0)

        policy = RetryPolicy(max_attempts=5, base_delay=1.0, max_backoff=30.0, timeout=50.0)
        transport = FakeTransport([rate_limited(), rate_limited(), ok_response()])
        result = send_with_retry(get_request(), transport, policy, clock=clock, sleep=custom_sleep)
        # After first sleep of 1s, clock jumps to 101.0 which exceeds deadline=50
        assert result.status == 429
        assert transport.call_count == 1  # only the initial attempt

    def test_deadline_exactly_met(self) -> None:
        """If clock() + delay == deadline (>=), do not retry."""
        clock = FakeClock(start=0.0)
        sleep = FakeSleeper(clock)
        policy = RetryPolicy(max_attempts=5, base_delay=1.0, max_backoff=30.0, timeout=1.0)
        transport = FakeTransport([rate_limited()])
        result = send_with_retry(get_request(), transport, policy, clock=clock, sleep=sleep)
        # delay=1.0, clock=0.0, deadline=1.0 → 0.0 + 1.0 >= 1.0 → no retry
        assert result.status == 429
        assert transport.call_count == 1

    def test_multiple_retries_within_deadline(self) -> None:
        clock = FakeClock(start=0.0)
        sleep = FakeSleeper(clock)
        policy = RetryPolicy(max_attempts=10, base_delay=1.0, max_backoff=30.0, timeout=10.0)
        transport = FakeTransport([
            rate_limited(), rate_limited(), rate_limited(), ok_response(),
        ])
        result = send_with_retry(get_request(), transport, policy, clock=clock, sleep=sleep)
        assert result.status == 200
        # Sleeps: 1+2+4=7 total, well within 10s


# ===================================================================
# Idempotency
# ===================================================================

class TestIdempotency:
    """Safe methods can retry; unsafe methods need Idempotency-Key."""

    def test_get_retries_without_key(self) -> None:
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        transport = FakeTransport([rate_limited(), ok_response()])
        result = send_with_retry(get_request(), transport, DEFAULT_POLICY, clock=clock, sleep=sleep)
        assert result.status == 200
        assert transport.call_count == 2

    def test_head_retries_without_key(self) -> None:
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        transport = FakeTransport([rate_limited(), ok_response()])
        result = send_with_retry(head_request(), transport, DEFAULT_POLICY, clock=clock, sleep=sleep)
        assert result.status == 200
        assert transport.call_count == 2

    def test_options_retries_without_key(self) -> None:
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        transport = FakeTransport([rate_limited(), ok_response()])
        result = send_with_retry(options_request(), transport, DEFAULT_POLICY, clock=clock, sleep=sleep)
        assert result.status == 200
        assert transport.call_count == 2

    def test_post_with_key_retries(self) -> None:
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        transport = FakeTransport([rate_limited(), ok_response()])
        req = post_request(idempotency_key="key-123")
        result = send_with_retry(req, transport, DEFAULT_POLICY, clock=clock, sleep=sleep)
        assert result.status == 200
        assert transport.call_count == 2

    def test_post_without_key_no_retry(self) -> None:
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        transport = FakeTransport([rate_limited()])
        req = post_request()
        result = send_with_retry(req, transport, DEFAULT_POLICY, clock=clock, sleep=sleep)
        assert result.status == 429
        assert transport.call_count == 1

    def test_post_with_empty_key_no_retry(self) -> None:
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        transport = FakeTransport([rate_limited()])
        req = post_request(idempotency_key="")
        result = send_with_retry(req, transport, DEFAULT_POLICY, clock=clock, sleep=sleep)
        assert result.status == 429
        assert transport.call_count == 1

    def test_key_preserved_across_retries(self) -> None:
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        transport = FakeTransport([rate_limited(), rate_limited(), ok_response()])
        policy = RetryPolicy(max_attempts=5, base_delay=1.0, max_backoff=30.0, timeout=120.0)
        req = post_request(idempotency_key="key-abc")
        send_with_retry(req, transport, policy, clock=clock, sleep=sleep)
        for call in transport.calls:
            assert call.headers.get("Idempotency-Key") == "key-abc"

    def test_request_not_mutated(self) -> None:
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        transport = FakeTransport([rate_limited(), ok_response()])
        req = Request(method="GET", url="https://test.example.com", headers={"X-Custom": "value"})
        original_headers = dict(req.headers)
        send_with_retry(req, transport, DEFAULT_POLICY, clock=clock, sleep=sleep)
        assert req.headers == original_headers

    def test_delete_without_key_no_retry(self) -> None:
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        transport = FakeTransport([rate_limited()])
        req = Request(method="DELETE", url="https://test.example.com")
        result = send_with_retry(req, transport, DEFAULT_POLICY, clock=clock, sleep=sleep)
        assert result.status == 429
        assert transport.call_count == 1

    def test_put_with_key_retries(self) -> None:
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        transport = FakeTransport([rate_limited(), ok_response()])
        req = Request(method="PUT", url="https://test.example.com", headers={"Idempotency-Key": "k1"})
        result = send_with_retry(req, transport, DEFAULT_POLICY, clock=clock, sleep=sleep)
        assert result.status == 200
        assert transport.call_count == 2


# ===================================================================
# Exception propagation
# ===================================================================

class TestExceptionPropagation:
    """Transport exceptions propagate unchanged."""

    def test_transport_exception_propagates(self) -> None:
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        transport = RaisingTransport(ConnectionError("network down"))
        with pytest.raises(ConnectionError, match="network down"):
            send_with_retry(get_request(), transport, DEFAULT_POLICY, clock=clock, sleep=sleep)

    def test_transport_timeout_propagates(self) -> None:
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        transport = RaisingTransport(TimeoutError("timed out"))
        with pytest.raises(TimeoutError, match="timed out"):
            send_with_retry(get_request(), transport, DEFAULT_POLICY, clock=clock, sleep=sleep)

    def test_custom_exception_propagates(self) -> None:
        class CustomTransportError(Exception):
            pass
        clock = FakeClock()
        sleep = FakeSleeper(clock)
        transport = RaisingTransport(CustomTransportError("custom"))
        with pytest.raises(CustomTransportError, match="custom"):
            send_with_retry(get_request(), transport, DEFAULT_POLICY, clock=clock, sleep=sleep)

    def test_exception_not_retried(self) -> None:
        """Transport that raises should only be called once."""
        call_count = 0
        exc = ConnectionError("fail")

        def counting_transport(req: Request) -> Response:
            nonlocal call_count
            call_count += 1
            raise exc

        clock = FakeClock()
        sleep = FakeSleeper(clock)
        with pytest.raises(ConnectionError):
            send_with_retry(get_request(), counting_transport, DEFAULT_POLICY, clock=clock, sleep=sleep)
        assert call_count == 1

