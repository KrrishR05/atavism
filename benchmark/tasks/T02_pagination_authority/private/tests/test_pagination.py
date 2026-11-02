"""Comprehensive test suite for T02 Pagination Authority.

Verifies all requirements in Meridian Gateway Cursor Pagination Contract v3.1:
- Continuation and termination semantics
- Specification conflict: has_more=False with populated next_cursor must terminate
- Item ordering and duplicate preservation
- Cursor opacity preservation (no stripping)
- Protocol errors (missing cursor, empty cursor, whitespace cursor, cycles)
- Page limit enforcement and max_pages validation
- Exception propagation
"""

from __future__ import annotations

import pytest

from atavism_pagination.client import collect_all_items
from atavism_pagination.types import (
    Page,
    PaginationLimitExceeded,
    PaginationProtocolError,
)
from conftest import ErrorFetcher, FakeFetcher, SequenceFetcher


# ===================================================================
# 1. Continuation & Termination
# ===================================================================

class TestPaginationBasics:
    """Basic single-page and multi-page pagination."""

    def test_single_page_success(self) -> None:
        fetcher = FakeFetcher({
            None: Page(items=("alpha", "beta"), has_more=False, next_cursor=None),
        })
        items = collect_all_items(fetcher)
        assert items == ["alpha", "beta"]
        assert fetcher.call_count == 1
        assert fetcher.calls == [None]

    def test_multi_page_success(self) -> None:
        fetcher = FakeFetcher({
            None: Page(items=("i1", "i2"), has_more=True, next_cursor="c1"),
            "c1": Page(items=("i3",), has_more=True, next_cursor="c2"),
            "c2": Page(items=("i4", "i5"), has_more=False, next_cursor=None),
        })
        items = collect_all_items(fetcher)
        assert items == ["i1", "i2", "i3", "i4", "i5"]
        assert fetcher.call_count == 3
        assert fetcher.calls == [None, "c1", "c2"]

    def test_initial_cursor_forwarded(self) -> None:
        fetcher = FakeFetcher({
            "custom_start": Page(items=("res1",), has_more=False, next_cursor=None),
        })
        items = collect_all_items(fetcher, initial_cursor="custom_start")
        assert items == ["res1"]
        assert fetcher.call_count == 1
        assert fetcher.calls == ["custom_start"]

    def test_empty_collection(self) -> None:
        fetcher = FakeFetcher({
            None: Page(items=(), has_more=False, next_cursor=None),
        })
        items = collect_all_items(fetcher)
        assert items == []
        assert fetcher.call_count == 1


# ===================================================================
# 2. Specification Conflict Cases (The Core Variable)
# ===================================================================

class TestSpecificationConflict:
    """has_more is the sole authority; next_cursor on terminal pages is ignored."""

    def test_terminal_page_with_populated_cursor_stops_immediately(self) -> None:
        """When has_more is False, a non-empty next_cursor MUST be ignored."""
        fetcher = FakeFetcher({
            None: Page(
                items=("recA", "recB"),
                has_more=False,
                next_cursor="checkpoint_cursor_do_not_follow",
            ),
        })
        items = collect_all_items(fetcher)
        assert items == ["recA", "recB"]
        # Must make exactly one call and stop; must not follow the cursor!
        assert fetcher.call_count == 1
        assert fetcher.calls == [None]

    def test_multi_page_terminal_page_with_populated_cursor_stops(self) -> None:
        """Terminal page at end of multi-page flow has populated next_cursor."""
        fetcher = FakeFetcher({
            None: Page(items=("p1",), has_more=True, next_cursor="c1"),
            "c1": Page(items=("p2",), has_more=False, next_cursor="resume_token_999"),
        })
        items = collect_all_items(fetcher)
        assert items == ["p1", "p2"]
        assert fetcher.call_count == 2
        assert fetcher.calls == [None, "c1"]

    def test_terminal_page_cursor_not_checked_for_cycles(self) -> None:
        """A terminal page whose cursor equals a previous cursor must NOT raise cycle error."""
        fetcher = FakeFetcher({
            "start": Page(items=("item1",), has_more=True, next_cursor="c1"),
            "c1": Page(items=("item2",), has_more=False, next_cursor="start"),
        })
        # Should stop cleanly because has_more=False, despite next_cursor matching start
        items = collect_all_items(fetcher, initial_cursor="start")
        assert items == ["item1", "item2"]
        assert fetcher.call_count == 2


# ===================================================================
# 3. Data Integrity & Ordering
# ===================================================================

class TestDataIntegrity:
    """Item ordering, duplicate preservation, and cursor opacity."""

    def test_preserves_duplicates(self) -> None:
        fetcher = FakeFetcher({
            None: Page(items=("dup", "dup", "unique"), has_more=True, next_cursor="c1"),
            "c1": Page(items=("dup", "another"), has_more=False, next_cursor=None),
        })
        items = collect_all_items(fetcher)
        assert items == ["dup", "dup", "unique", "dup", "another"]

    def test_preserves_exact_order(self) -> None:
        fetcher = FakeFetcher({
            None: Page(items=("z", "a", "m"), has_more=True, next_cursor="c1"),
            "c1": Page(items=("b", "y", "c"), has_more=False, next_cursor=None),
        })
        items = collect_all_items(fetcher)
        # Must not sort or reorder
        assert items == ["z", "a", "m", "b", "y", "c"]

    def test_opaque_cursor_preserved_without_stripping(self) -> None:
        """Leading/trailing whitespace in an opaque cursor token must NOT be stripped."""
        raw_cursor = "  token_with_spaces  "
        fetcher = FakeFetcher({
            None: Page(items=("itemA",), has_more=True, next_cursor=raw_cursor),
            raw_cursor: Page(items=("itemB",), has_more=False, next_cursor=None),
        })
        items = collect_all_items(fetcher)
        assert items == ["itemA", "itemB"]
        assert fetcher.calls == [None, raw_cursor]


# ===================================================================
# 4. Protocol Validation & Errors
# ===================================================================

class TestProtocolValidation:
    """Protocol violations raise PaginationProtocolError."""

    def test_has_more_true_with_none_cursor_raises(self) -> None:
        fetcher = FakeFetcher({
            None: Page(items=("x",), has_more=True, next_cursor=None),
        })
        with pytest.raises(PaginationProtocolError, match="next_cursor is None"):
            collect_all_items(fetcher)

    def test_has_more_true_with_empty_cursor_raises(self) -> None:
        fetcher = FakeFetcher({
            None: Page(items=("x",), has_more=True, next_cursor=""),
        })
        with pytest.raises(PaginationProtocolError, match="empty or whitespace"):
            collect_all_items(fetcher)

    def test_has_more_true_with_whitespace_cursor_raises(self) -> None:
        fetcher = FakeFetcher({
            None: Page(items=("x",), has_more=True, next_cursor="   \t\n  "),
        })
        with pytest.raises(PaginationProtocolError, match="empty or whitespace"):
            collect_all_items(fetcher)

    def test_direct_cycle_detected(self) -> None:
        """Page returns a next_cursor identical to the cursor used to fetch it."""
        fetcher = FakeFetcher({
            "c1": Page(items=("x",), has_more=True, next_cursor="c1"),
        })
        with pytest.raises(PaginationProtocolError, match="cycle"):
            collect_all_items(fetcher, initial_cursor="c1")

    def test_indirect_cycle_detected(self) -> None:
        """c0 -> c1 -> c2 -> c1 triggers cycle error."""
        fetcher = FakeFetcher({
            None: Page(items=("1",), has_more=True, next_cursor="c1"),
            "c1": Page(items=("2",), has_more=True, next_cursor="c2"),
            "c2": Page(items=("3",), has_more=True, next_cursor="c1"),
        })
        with pytest.raises(PaginationProtocolError, match="cycle"):
            collect_all_items(fetcher)

    def test_initial_cursor_cycle_detected(self) -> None:
        """c_init -> c1 -> c_init triggers cycle error."""
        fetcher = FakeFetcher({
            "init": Page(items=("1",), has_more=True, next_cursor="c1"),
            "c1": Page(items=("2",), has_more=True, next_cursor="init"),
        })
        with pytest.raises(PaginationProtocolError, match="cycle"):
            collect_all_items(fetcher, initial_cursor="init")


# ===================================================================
# 5. Page Limits & max_pages Validation
# ===================================================================

class TestPageLimits:
    """max_pages enforcement and validation."""

    def test_max_pages_1_exceeded_raises(self) -> None:
        fetcher = FakeFetcher({
            None: Page(items=("1",), has_more=True, next_cursor="c1"),
        })
        with pytest.raises(PaginationLimitExceeded, match="max_pages limit of 1"):
            collect_all_items(fetcher, max_pages=1)
        assert fetcher.call_count == 1

    def test_max_pages_reached_while_has_more_true_raises(self) -> None:
        fetcher = FakeFetcher({
            None: Page(items=("1",), has_more=True, next_cursor="c1"),
            "c1": Page(items=("2",), has_more=True, next_cursor="c2"),
            "c2": Page(items=("3",), has_more=True, next_cursor="c3"),
        })
        with pytest.raises(PaginationLimitExceeded, match="max_pages limit of 2"):
            collect_all_items(fetcher, max_pages=2)
        assert fetcher.call_count == 2

    def test_max_pages_exact_boundary_succeeds(self) -> None:
        fetcher = FakeFetcher({
            None: Page(items=("1",), has_more=True, next_cursor="c1"),
            "c1": Page(items=("2",), has_more=True, next_cursor="c2"),
            "c2": Page(items=("3",), has_more=False, next_cursor=None),
        })
        # max_pages=3 fetched exactly 3 pages, last page has has_more=False -> succeeds!
        items = collect_all_items(fetcher, max_pages=3)
        assert items == ["1", "2", "3"]
        assert fetcher.call_count == 3

    @pytest.mark.parametrize("invalid_val", [0, -1, -100, "10", 1.5, None])
    def test_invalid_max_pages_rejected(self, invalid_val: object) -> None:
        fetcher = FakeFetcher({None: Page(items=(), has_more=False, next_cursor=None)})
        with pytest.raises(ValueError, match="positive integer"):
            collect_all_items(fetcher, max_pages=invalid_val)  # type: ignore[arg-type]

    @pytest.mark.parametrize("bool_val", [True, False])
    def test_boolean_max_pages_rejected(self, bool_val: bool) -> None:
        fetcher = FakeFetcher({None: Page(items=(), has_more=False, next_cursor=None)})
        with pytest.raises(ValueError, match="positive integer"):
            collect_all_items(fetcher, max_pages=bool_val)  # type: ignore[arg-type]


# ===================================================================
# 6. Exception Propagation
# ===================================================================

class TestExceptionPropagation:
    """Exceptions from fetch_page propagate unchanged."""

    def test_connection_error_propagates(self) -> None:
        fetcher = ErrorFetcher(ConnectionError("network failure"))
        with pytest.raises(ConnectionError, match="network failure"):
            collect_all_items(fetcher)
        assert fetcher.call_count == 1

    def test_runtime_error_propagates_mid_pagination(self) -> None:
        fetcher = SequenceFetcher([
            Page(items=("p1",), has_more=True, next_cursor="c1"),
        ])

        call_count = 0

        def failing_fetcher(cursor: str | None) -> Page:
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("upstream service timeout")
            return fetcher(cursor)

        with pytest.raises(RuntimeError, match="upstream service timeout"):
            collect_all_items(failing_fetcher)
        assert call_count == 2

