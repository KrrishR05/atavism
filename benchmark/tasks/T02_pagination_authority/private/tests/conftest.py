"""Shared test fixtures and helpers for T02 pagination authority grading."""

from __future__ import annotations

from typing import Sequence

from atavism_pagination.types import Page


class FakeFetcher:
    """A deterministic programmable page fetcher."""

    def __init__(self, pages_by_cursor: dict[str | None, Page]) -> None:
        self._pages = dict(pages_by_cursor)
        self._calls: list[str | None] = []

    def __call__(self, cursor: str | None) -> Page:
        self._calls.append(cursor)
        if cursor not in self._pages:
            raise KeyError(f"Unexpected cursor passed to FakeFetcher: {cursor!r}")
        return self._pages[cursor]

    @property
    def call_count(self) -> int:
        return len(self._calls)

    @property
    def calls(self) -> list[str | None]:
        return list(self._calls)


class SequenceFetcher:
    """A fetcher that yields pages sequentially from a predefined list."""

    def __init__(self, pages: Sequence[Page]) -> None:
        self._pages = list(pages)
        self._calls: list[str | None] = []

    def __call__(self, cursor: str | None) -> Page:
        self._calls.append(cursor)
        if not self._pages:
            raise RuntimeError("SequenceFetcher exhausted: no more pages configured")
        return self._pages.pop(0)

    @property
    def call_count(self) -> int:
        return len(self._calls)

    @property
    def calls(self) -> list[str | None]:
        return list(self._calls)


class ErrorFetcher:
    """A fetcher that raises an exception on a specified call index."""

    def __init__(self, exception: Exception, fail_on_call: int = 1) -> None:
        self._exception = exception
        self._fail_on_call = fail_on_call
        self._calls: list[str | None] = []

    def __call__(self, cursor: str | None) -> Page:
        self._calls.append(cursor)
        if len(self._calls) == self._fail_on_call:
            raise self._exception
        return Page(items=("recovered",), has_more=False, next_cursor=None)

    @property
    def call_count(self) -> int:
        return len(self._calls)

