"""Shared test fixtures and helpers for T01 retry semantics grading."""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from typing import Callable

import pytest

from atavism_retry.types import Clock, Request, Response, RetryPolicy, Sleeper, Transport


# ---------------------------------------------------------------------------
# Fake transport
# ---------------------------------------------------------------------------

class FakeTransport:
    """A programmable transport that returns responses from a sequence."""

    def __init__(self, responses: list[Response]) -> None:
        self._responses = list(responses)
        self._calls: list[Request] = []

    def __call__(self, request: Request) -> Response:
        self._calls.append(request)
        if not self._responses:
            raise RuntimeError("FakeTransport exhausted: no more responses")
        return self._responses.pop(0)

    @property
    def call_count(self) -> int:
        return len(self._calls)

    @property
    def calls(self) -> list[Request]:
        return list(self._calls)


class RaisingTransport:
    """A transport that raises a specified exception."""

    def __init__(self, exception: Exception) -> None:
        self._exception = exception

    def __call__(self, request: Request) -> Response:
        raise self._exception


# ---------------------------------------------------------------------------
# Fake clock
# ---------------------------------------------------------------------------

class FakeClock:
    """A deterministic clock that advances explicitly."""

    def __init__(self, start: float = 0.0) -> None:
        self._now = start

    def __call__(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds


# ---------------------------------------------------------------------------
# Fake sleeper
# ---------------------------------------------------------------------------

class FakeSleeper:
    """Records sleep calls and advances a coupled clock."""

    def __init__(self, clock: FakeClock) -> None:
        self._clock = clock
        self._sleeps: list[float] = []

    def __call__(self, seconds: float) -> None:
        self._sleeps.append(seconds)
        self._clock.advance(seconds)

    @property
    def sleep_calls(self) -> list[float]:
        return list(self._sleeps)


# ---------------------------------------------------------------------------
# Standard responses
# ---------------------------------------------------------------------------

def ok_response(body: bytes = b"OK") -> Response:
    return Response(status=200, body=body)


def rate_limited(retry_after: str | None = None, error_code: str = "RATE_LIMITED") -> Response:
    headers = {}
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    return Response(status=429, error_code=error_code, headers=headers)


def temporarily_unavailable(retry_after: str | None = None) -> Response:
    headers = {}
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    return Response(status=503, error_code="TEMPORARY_UNAVAILABLE", headers=headers)


def lease_busy(retry_after: str | None = None) -> Response:
    headers = {}
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    return Response(status=409, error_code="LEASE_BUSY", headers=headers)


def conflict_other() -> Response:
    return Response(status=409, error_code="OTHER_CONFLICT")


def bad_request() -> Response:
    return Response(status=400, error_code="BAD_REQUEST")


def internal_error() -> Response:
    return Response(status=500, error_code="INTERNAL_ERROR")


# ---------------------------------------------------------------------------
# Standard requests
# ---------------------------------------------------------------------------

def get_request(url: str = "https://api.meridian.test/v1/resource") -> Request:
    return Request(method="GET", url=url)


def post_request(
    url: str = "https://api.meridian.test/v1/resource",
    idempotency_key: str | None = None,
) -> Request:
    headers: dict[str, str] = {}
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    return Request(method="POST", url=url, headers=headers)


def head_request(url: str = "https://api.meridian.test/v1/resource") -> Request:
    return Request(method="HEAD", url=url)


def options_request(url: str = "https://api.meridian.test/v1/resource") -> Request:
    return Request(method="OPTIONS", url=url)


# ---------------------------------------------------------------------------
# Default policy
# ---------------------------------------------------------------------------

DEFAULT_POLICY = RetryPolicy(
    max_attempts=3,
    base_delay=1.0,
    max_backoff=30.0,
    timeout=120.0,
)

