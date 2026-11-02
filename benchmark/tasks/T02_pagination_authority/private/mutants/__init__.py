"""Mutation fixtures for T02 — deliberately incorrect implementations.

Each mutant embodies a specific engineering or specification failure mode
to validate that the test suite detects and rejects it.
"""

from __future__ import annotations

from atavism_pagination.types import (
    Page,
    PageFetcher,
    PaginationLimitExceeded,
    PaginationProtocolError,
)


# ---------------------------------------------------------------------------
# Mutant 1: cursor_driven_continuation
# Follows the legacy inline comment: continues whenever next_cursor is populated,
# treating has_more as informational.
# ---------------------------------------------------------------------------

def mutant_cursor_driven_continuation(
    fetch_page: PageFetcher,
    *,
    initial_cursor: str | None = None,
    max_pages: int = 100,
) -> list[str]:
    """DEFECT: Follows legacy comment; continues if next_cursor is populated."""
    if isinstance(max_pages, bool) or not isinstance(max_pages, int) or max_pages <= 0:
        raise ValueError(f"max_pages must be positive integer: {max_pages}")

    all_items: list[str] = []
    current_cursor: str | None = initial_cursor
    pages_fetched = 0

    while True:
        page = fetch_page(current_cursor)
        pages_fetched += 1
        all_items.extend(page.items)

        # DEFECT: ignores has_more! Continues whenever next_cursor is populated
        if not page.next_cursor:
            return all_items

        if pages_fetched >= max_pages:
            raise PaginationLimitExceeded("limit reached")

        current_cursor = page.next_cursor


# ---------------------------------------------------------------------------
# Mutant 2: has_more_as_advisory
# Checks has_more, but if next_cursor is present, continues anyway.
# ---------------------------------------------------------------------------

def mutant_has_more_as_advisory(
    fetch_page: PageFetcher,
    *,
    initial_cursor: str | None = None,
    max_pages: int = 100,
) -> list[str]:
    """DEFECT: Treats has_more as advisory; continues if next_cursor is present."""
    if isinstance(max_pages, bool) or not isinstance(max_pages, int) or max_pages <= 0:
        raise ValueError("Invalid max_pages")

    all_items: list[str] = []
    current_cursor: str | None = initial_cursor
    pages_fetched = 0

    while True:
        page = fetch_page(current_cursor)
        pages_fetched += 1
        all_items.extend(page.items)

        # DEFECT: Even if has_more is False, if next_cursor is provided, keeps going
        if not page.has_more and not page.next_cursor:
            return all_items

        if pages_fetched >= max_pages:
            raise PaginationLimitExceeded("limit reached")

        next_cur = page.next_cursor
        if next_cur is None or not next_cur.strip():
            return all_items

        current_cursor = next_cur


# ---------------------------------------------------------------------------
# Mutant 3: stop_when_missing_cursor
# When has_more=True but next_cursor is missing, stops and returns partial items
# instead of raising PaginationProtocolError.
# ---------------------------------------------------------------------------

def mutant_stop_when_missing_cursor(
    fetch_page: PageFetcher,
    *,
    initial_cursor: str | None = None,
    max_pages: int = 100,
) -> list[str]:
    """DEFECT: Silently stops on missing cursor instead of raising protocol error."""
    if isinstance(max_pages, bool) or not isinstance(max_pages, int) or max_pages <= 0:
        raise ValueError("Invalid max_pages")

    all_items: list[str] = []
    current_cursor: str | None = initial_cursor
    pages_fetched = 0

    while True:
        page = fetch_page(current_cursor)
        pages_fetched += 1
        all_items.extend(page.items)

        if not page.has_more:
            return all_items

        if pages_fetched >= max_pages:
            raise PaginationLimitExceeded("limit reached")

        # DEFECT: If next_cursor is missing, stops quietly instead of raising error
        if not page.next_cursor or not page.next_cursor.strip():
            return all_items

        current_cursor = page.next_cursor


# ---------------------------------------------------------------------------
# Mutant 4: deduplicate_items
# Drops duplicate items during aggregation.
# ---------------------------------------------------------------------------

def mutant_deduplicate_items(
    fetch_page: PageFetcher,
    *,
    initial_cursor: str | None = None,
    max_pages: int = 100,
) -> list[str]:
    """DEFECT: Deduplicates records during aggregation."""
    if isinstance(max_pages, bool) or not isinstance(max_pages, int) or max_pages <= 0:
        raise ValueError("Invalid max_pages")

    all_items: list[str] = []
    seen_cursors: set[str | None] = set()
    current_cursor: str | None = initial_cursor
    pages_fetched = 0

    while True:
        seen_cursors.add(current_cursor)
        page = fetch_page(current_cursor)
        pages_fetched += 1

        all_items.extend(page.items)

        if not page.has_more:
            # DEFECT: Deduplicates before returning
            return list(dict.fromkeys(all_items))

        if pages_fetched >= max_pages:
            raise PaginationLimitExceeded("limit reached")

        next_cur = page.next_cursor
        if next_cur is None or not next_cur.strip():
            raise PaginationProtocolError("invalid cursor")
        if next_cur in seen_cursors:
            raise PaginationProtocolError("cycle")

        current_cursor = next_cur


# ---------------------------------------------------------------------------
# Mutant 5: sort_items
# Sorts aggregated items before returning.
# ---------------------------------------------------------------------------

def mutant_sort_items(
    fetch_page: PageFetcher,
    *,
    initial_cursor: str | None = None,
    max_pages: int = 100,
) -> list[str]:
    """DEFECT: Re-orders / sorts records before returning."""
    if isinstance(max_pages, bool) or not isinstance(max_pages, int) or max_pages <= 0:
        raise ValueError("Invalid max_pages")

    all_items: list[str] = []
    seen_cursors: set[str | None] = set()
    current_cursor: str | None = initial_cursor
    pages_fetched = 0

    while True:
        seen_cursors.add(current_cursor)
        page = fetch_page(current_cursor)
        pages_fetched += 1

        all_items.extend(page.items)

        if not page.has_more:
            # DEFECT: sorts items
            return sorted(all_items)

        if pages_fetched >= max_pages:
            raise PaginationLimitExceeded("limit reached")

        next_cur = page.next_cursor
        if next_cur is None or not next_cur.strip():
            raise PaginationProtocolError("invalid cursor")
        if next_cur in seen_cursors:
            raise PaginationProtocolError("cycle")

        current_cursor = next_cur


# ---------------------------------------------------------------------------
# Mutant 6: strip_cursor
# Strips whitespace from opaque cursor tokens before forwarding.
# ---------------------------------------------------------------------------

def mutant_strip_cursor(
    fetch_page: PageFetcher,
    *,
    initial_cursor: str | None = None,
    max_pages: int = 100,
) -> list[str]:
    """DEFECT: Strips whitespace from opaque cursor tokens."""
    if isinstance(max_pages, bool) or not isinstance(max_pages, int) or max_pages <= 0:
        raise ValueError("Invalid max_pages")

    all_items: list[str] = []
    seen_cursors: set[str | None] = set()
    current_cursor: str | None = initial_cursor
    pages_fetched = 0

    while True:
        seen_cursors.add(current_cursor)
        page = fetch_page(current_cursor)
        pages_fetched += 1

        all_items.extend(page.items)

        if not page.has_more:
            return all_items

        if pages_fetched >= max_pages:
            raise PaginationLimitExceeded("limit reached")

        next_cur = page.next_cursor
        if next_cur is None or not next_cur.strip():
            raise PaginationProtocolError("invalid cursor")

        # DEFECT: modifies opaque cursor by stripping whitespace
        current_cursor = next_cur.strip()


# ---------------------------------------------------------------------------
# Mutant 7: no_cycle_detection
# Fails to track cursors and detect cycles.
# ---------------------------------------------------------------------------

def mutant_no_cycle_detection(
    fetch_page: PageFetcher,
    *,
    initial_cursor: str | None = None,
    max_pages: int = 100,
) -> list[str]:
    """DEFECT: Fails to detect repeated cursors (no cycle detection)."""
    if isinstance(max_pages, bool) or not isinstance(max_pages, int) or max_pages <= 0:
        raise ValueError("Invalid max_pages")

    all_items: list[str] = []
    current_cursor: str | None = initial_cursor
    pages_fetched = 0

    while True:
        page = fetch_page(current_cursor)
        pages_fetched += 1

        all_items.extend(page.items)

        if not page.has_more:
            return all_items

        if pages_fetched >= max_pages:
            raise PaginationLimitExceeded("limit reached")

        next_cur = page.next_cursor
        if next_cur is None or not next_cur.strip():
            raise PaginationProtocolError("invalid cursor")

        # DEFECT: no cycle check
        current_cursor = next_cur


# ---------------------------------------------------------------------------
# Mutant 8: silent_partial_on_limit
# Silently returns partial results when max_pages is exceeded.
# ---------------------------------------------------------------------------

def mutant_silent_partial_on_limit(
    fetch_page: PageFetcher,
    *,
    initial_cursor: str | None = None,
    max_pages: int = 100,
) -> list[str]:
    """DEFECT: Silently returns partial results on page limit."""
    if isinstance(max_pages, bool) or not isinstance(max_pages, int) or max_pages <= 0:
        raise ValueError("Invalid max_pages")

    all_items: list[str] = []
    seen_cursors: set[str | None] = set()
    current_cursor: str | None = initial_cursor
    pages_fetched = 0

    while True:
        seen_cursors.add(current_cursor)
        page = fetch_page(current_cursor)
        pages_fetched += 1

        all_items.extend(page.items)

        if not page.has_more:
            return all_items

        # DEFECT: silently returns partial result instead of raising
        if pages_fetched >= max_pages:
            return all_items

        next_cur = page.next_cursor
        if next_cur is None or not next_cur.strip():
            raise PaginationProtocolError("invalid cursor")
        if next_cur in seen_cursors:
            raise PaginationProtocolError("cycle")

        current_cursor = next_cur


# ---------------------------------------------------------------------------
# Mutant 9: swallow_exceptions
# Swallows fetcher exceptions and returns whatever items were collected.
# ---------------------------------------------------------------------------

def mutant_swallow_exceptions(
    fetch_page: PageFetcher,
    *,
    initial_cursor: str | None = None,
    max_pages: int = 100,
) -> list[str]:
    """DEFECT: Swallows fetcher exceptions and returns partial data."""
    if isinstance(max_pages, bool) or not isinstance(max_pages, int) or max_pages <= 0:
        raise ValueError("Invalid max_pages")

    all_items: list[str] = []
    seen_cursors: set[str | None] = set()
    current_cursor: str | None = initial_cursor
    pages_fetched = 0

    while True:
        seen_cursors.add(current_cursor)
        try:
            page = fetch_page(current_cursor)
        except Exception:
            # DEFECT: swallows exception
            return all_items

        pages_fetched += 1
        all_items.extend(page.items)

        if not page.has_more:
            return all_items

        if pages_fetched >= max_pages:
            raise PaginationLimitExceeded("limit reached")

        next_cur = page.next_cursor
        if next_cur is None or not next_cur.strip():
            raise PaginationProtocolError("invalid cursor")
        if next_cur in seen_cursors:
            raise PaginationProtocolError("cycle")

        current_cursor = next_cur

