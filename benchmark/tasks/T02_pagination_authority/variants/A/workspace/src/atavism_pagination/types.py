"""Meridian Gateway pagination client — type definitions.

Do not modify this file. Implement your solution in client.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Page:
    """A single page of paginated results."""
    items: tuple[str, ...]
    has_more: bool
    next_cursor: str | None = None


class PaginationProtocolError(ValueError):
    """Raised when the pagination protocol is violated by the server."""


class PaginationLimitExceeded(RuntimeError):
    """Raised when the maximum page limit is reached while more pages remain."""


class PageFetcher(Protocol):
    """Callable that fetches a page given an opaque cursor token."""
    def __call__(self, cursor: str | None) -> Page: ...

