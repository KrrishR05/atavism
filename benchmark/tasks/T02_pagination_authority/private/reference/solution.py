"""Reference solution for T02 Pagination Authority.

Strictly follows Meridian Gateway Cursor Pagination Contract v3.1:
- has_more is the sole authority for continuation.
- next_cursor on terminal pages (has_more=False) is ignored.
- next_cursor when has_more=True must be a non-empty, non-whitespace string.
- Detects pagination cycles (repeated cursors).
- Validates max_pages (> 0, non-bool integer) and raises PaginationLimitExceeded.
- Preserves order and duplicate items.
- Propagates fetcher exceptions unchanged.
"""

from __future__ import annotations

from atavism_pagination.types import (
    Page,
    PageFetcher,
    PaginationLimitExceeded,
    PaginationProtocolError,
)


def collect_all_items(
    fetch_page: PageFetcher,
    *,
    initial_cursor: str | None = None,
    max_pages: int = 100,
) -> list[str]:
    """Retrieve all records across multiple pages according to contract.md."""
    if isinstance(max_pages, bool) or not isinstance(max_pages, int) or max_pages <= 0:
        raise ValueError(f"max_pages must be a positive integer, got {max_pages!r}")

    all_items: list[str] = []
    seen_cursors: set[str | None] = set()
    current_cursor: str | None = initial_cursor
    pages_fetched = 0

    while True:
        seen_cursors.add(current_cursor)
        page = fetch_page(current_cursor)
        pages_fetched += 1

        all_items.extend(page.items)

        # Continuation rule: has_more is the sole authority
        if not page.has_more:
            # Terminal page: stop immediately, ignore next_cursor
            return all_items

        # has_more is True: check page limit before attempting next page
        if pages_fetched >= max_pages:
            raise PaginationLimitExceeded(
                f"Reached max_pages limit of {max_pages} while has_more is True"
            )

        next_cur = page.next_cursor
        if next_cur is None:
            raise PaginationProtocolError("Server declared has_more=True but next_cursor is None")
        if not isinstance(next_cur, str):
            raise PaginationProtocolError(f"next_cursor must be a string, got {type(next_cur).__name__}")
        if not next_cur.strip():
            raise PaginationProtocolError("Server declared has_more=True but next_cursor is empty or whitespace-only")

        if next_cur in seen_cursors:
            raise PaginationProtocolError(
                f"Pagination cycle detected: cursor {next_cur!r} has already been requested"
            )

        current_cursor = next_cur

