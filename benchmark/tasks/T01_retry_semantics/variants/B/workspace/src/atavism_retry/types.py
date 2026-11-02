"""Meridian Gateway retry client — type definitions.

Do not modify this file. Implement your solution in client.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class Request:
    """An HTTP request."""
    method: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes | None = None


@dataclass(frozen=True)
class Response:
    """An HTTP response."""
    status: int
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    error_code: str = ""


@dataclass(frozen=True)
class RetryPolicy:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_backoff: float = 30.0
    timeout: float = 120.0


class Transport(Protocol):
    """Sends a request and returns a response. May raise exceptions."""
    def __call__(self, request: Request) -> Response: ...


class Clock(Protocol):
    """Returns the current monotonic time in seconds."""
    def __call__(self) -> float: ...


class Sleeper(Protocol):
    """Sleeps for the given number of seconds."""
    def __call__(self, seconds: float) -> None: ...

