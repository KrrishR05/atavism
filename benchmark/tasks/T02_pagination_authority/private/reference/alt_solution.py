"""Alternative valid reference implementation for T02 Pagination Authority.

Serves as a positive control to verify grader independence from coding style.
Uses a generator-based architecture to separate page retrieval from collection.
"""

from __future__ import annotations

from typing import Iterator

from atavism_pagination.types import (
    Page,
    PageFetcher,
    PaginationLimitExceeded,
    PaginationProtocolError,
)


def _validate_max_pages(limit: object) -> int:
    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
        raise ValueError(f"max_pages must be a positive integer, got {limit!r}")
    return limit


def _iter_pages(
    fetcher: PageFetcher,
    start_cursor: str | None,
    limit: int,
) -> Iterator[Page]:
    """Yield pages one by one according to contract rules."""
    cursor: str | None = start_cursor
    visited_cursors: set[str | None] = set()
    count = 0

    while True:
        visited_cursors.add(cursor)
        page = fetcher(cursor)
        count += 1
        yield page

        # Terminal condition: has_more is the sole authority
        if not page.has_more:
            break

        # Check limit before advancing to next page
        if count >= limit:
            raise PaginationLimitExceeded(
                f"Fetched {count} pages with more remaining (max_pages={limit})"
            )

        token = page.next_cursor
        if token is None:
            raise PaginationProtocolError("Page declared has_more=True but next_cursor is None")
        if not isinstance(token, str):
            raise PaginationProtocolError(f"Cursor token must be a string, got {type(token).__name__}")
        if not token.strip():
            raise PaginationProtocolError("Cursor token must contain non-whitespace characters")
        if token in visited_cursors:
            raise PaginationProtocolError(f"Detected repeated cursor in pagination sequence: {token!r}")

        cursor = token


def collect_all_items(
    fetch_page: PageFetcher,
    *,
    initial_cursor: str | None = None,
    max_pages: int = 100,
) -> list[str]:
    """Retrieve all records across multiple pages using page generator."""
    validated_limit = _validate_max_pages(max_pages)
    records: list[str] = []

    for page in _iter_pages(fetch_page, initial_cursor, validated_limit):
        records.extend(page.items)

    return records

