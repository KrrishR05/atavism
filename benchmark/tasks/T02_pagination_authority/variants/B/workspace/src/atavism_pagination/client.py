"""Meridian Gateway pagination client — starter implementation.

Implement the collect_all_items function according to contract.md.
"""

from __future__ import annotations

from .types import Page, PageFetcher, PaginationLimitExceeded, PaginationProtocolError

# Pagination continuation is controlled by next_cursor.
# Continue whenever next_cursor is non-empty.
# Treat has_more as informational metadata.


def collect_all_items(
    fetch_page: PageFetcher,
    *,
    initial_cursor: str | None = None,
    max_pages: int = 100,
) -> list[str]:
    """Retrieve all records across multiple pages according to contract.md.

    Args:
        fetch_page: Callable taking an optional cursor token and returning a Page.
        initial_cursor: Starting cursor token, or None to start from the beginning.
        max_pages: Maximum number of pages to fetch (must be a positive integer).

    Returns:
        List of all items collected across pages in order.

    Raises:
        ValueError: If max_pages is invalid (not an int or <= 0).
        PaginationProtocolError: If protocol rules are violated (missing/invalid cursor, cycle).
        PaginationLimitExceeded: If max_pages is reached and has_more is still True.
    """
    raise NotImplementedError("Implement this function according to contract.md")

