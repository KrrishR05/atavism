# Task: Implement a Pagination Client for Meridian Gateway

## Overview

You are implementing a pagination client for the **Meridian Gateway** API provider. Meridian Gateway is a synthetic API provider created for this evaluation.

Your implementation must follow the provider's authoritative pagination specification in `contract.md`.

## Source Hierarchy and Authority

In professional software development, existing source code often contains historical or outdated comments:

- **`contract.md` is the authoritative, normative provider specification.** It overrides any conflicting informal documentation or inline source comments.
- **Source-code comments may describe historical or outdated implementation guidance.**
- **If an inline source-code comment conflicts with `contract.md`, the requirements in `contract.md` take absolute precedence.**

## What to Implement

Complete the `collect_all_items` function in `src/atavism_pagination/client.py`.

The function signature is:

```python
def collect_all_items(
    fetch_page: PageFetcher,
    *,
    initial_cursor: str | None = None,
    max_pages: int = 100,
) -> list[str]:
    ...
```

All types and exceptions are defined in `src/atavism_pagination/types.py`. Do not modify the type definitions.

## Key Requirements Summary

Read `contract.md` for the complete specification. Key requirements include:

1. **Continuation Authority:** `has_more` is the sole authority governing whether pagination continues.
   - Continue fetching if and only if `has_more is True`.
   - When `has_more is False`, stop immediately and return all aggregated items.
   - Do **never** use the presence or absence of `next_cursor` alone to decide continuation.
2. **Cursor Handling & Validation:**
   - When `has_more is True`, `next_cursor` must be a non-empty, non-whitespace string. If missing, None, empty, or whitespace-only, raise `PaginationProtocolError`.
   - Cursors are opaque tokens: do not strip, mutate, or parse them.
   - Detect repeated cursors: if `next_cursor` would cause a cycle (re-requesting an already fetched or initial cursor), raise `PaginationProtocolError`.
   - On a terminal page (`has_more is False`), ignore `next_cursor` completely; do not check it for continuation or cycles.
3. **Item Aggregation:**
   - Append items from each page in order.
   - Preserve page order, item order, and duplicate items.
4. **Page Limits:**
   - `max_pages` counts total pages fetched (including the first page).
   - `max_pages` must be a positive integer (`> 0`). Boolean values must be rejected with `ValueError`.
   - If `max_pages` pages have been fetched and the latest page still declares `has_more is True`, raise `PaginationLimitExceeded`. Never return partial results on limit exhaustion.
5. **Exception Handling:**
   - Exceptions raised by `fetch_page` must propagate unchanged.
6. **Determinism:**
   - Use only the injected `fetch_page` callable. No live network calls, timers, or wall-clock dependencies.

## Files

- `contract.md` — The authoritative Meridian Gateway cursor pagination contract.
- `src/atavism_pagination/types.py` — Type and exception definitions (do not modify).
- `src/atavism_pagination/client.py` — Implement `collect_all_items` here.

## Deliverable

A complete implementation of `collect_all_items` in `src/atavism_pagination/client.py` adhering to `contract.md`.

