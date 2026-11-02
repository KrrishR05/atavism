# Meridian Gateway — Cursor Pagination Contract v3.1

*This document is the authoritative, normative specification for cursor-based pagination when interacting with the Meridian Gateway API.*

## 1. Page Structure

Every call to `fetch_page(cursor)` returns a `Page` object with three fields:

- `items`: A tuple of strings representing the records on this page.
- `has_more`: A boolean indicating whether additional records exist that must be retrieved.
- `next_cursor`: An optional opaque string token (`str | None`) pointing to the subsequent page.

## 2. Continuation Semantics (The Rule of Authority)

**`has_more` is the sole authority for deciding whether pagination continues.**

The presence or absence of `next_cursor` alone must never trigger another request. The client must adhere to the following decision matrix:

| `has_more` | `next_cursor` | Client Action |
|---|---|---|
| `True` | Non-empty string | **Continue:** Request next page using `cursor=next_cursor`. |
| `True` | `None` | **Protocol Error:** Raise `PaginationProtocolError`. |
| `True` | Empty string (`""`) or whitespace-only | **Protocol Error:** Raise `PaginationProtocolError`. |
| `False` | `None` | **Terminate:** Stop pagination immediately and return aggregated items. |
| `False` | Non-empty string | **Terminate:** Stop pagination immediately; ignore `next_cursor`. |

### Important Contract Clarifications:
- A terminal page (`has_more is False`) may contain a non-null cursor for downstream client checkpointing or stream resumption. This cursor **does not authorize another page request**.
- If `has_more is False`, pagination must stop immediately, even if `next_cursor` contains a non-empty token.

## 3. Cursor Validation & Opacity

When `has_more is True`, a valid cursor token is mandatory to fetch the next page:

1. **Token Type:** `next_cursor` must be an instance of `str`.
2. **Non-Empty:** `next_cursor` must contain at least one non-whitespace character.
3. **Opacity:** Cursors are opaque identifiers. The client must **not** strip whitespace, mutate, or attempt to parse cursor values. The exact token received must be forwarded to `fetch_page`.
4. **Cycle Detection:** The client must track all cursor tokens fetched (including `initial_cursor`). If `next_cursor` matches `initial_cursor` or any previously fetched cursor, the client must raise `PaginationProtocolError` to prevent an infinite pagination loop.
5. **Terminal Exemption:** A cursor present on a terminal page (`has_more is False`) is ignored for continuation and must **not** be validated for cycles or non-whitespace content.

## 4. Initial Request & Item Aggregation

1. **Initial Call:** The client begins pagination by calling `fetch_page(initial_cursor)`. A value of `initial_cursor=None` is valid and represents fetching from the start of the collection.
2. **Item Order:** Items must be aggregated in the exact order received across pages.
3. **Duplicate Preservation:** If an item appears multiple times across or within pages, all occurrences must be preserved. The client must never deduplicate or re-sort records.

## 5. Page Limits

1. **Accounting:** `max_pages` specifies the maximum total number of pages the client may fetch, including the initial page.
2. **Type Validation:** `max_pages` must be a strictly positive integer (`max_pages > 0`). Boolean values (`True`, `False`) must be rejected with a `ValueError`.
3. **Limit Enforcement:** If `max_pages` pages have been fetched and the latest page declares `has_more is True`, the client must raise `PaginationLimitExceeded`.
4. **No Partial Returns:** The client must never silently return an incomplete list of items when `max_pages` is exceeded.

## 6. Exception Handling & Determinism

1. **Exception Propagation:** If `fetch_page` raises any exception (e.g. `ConnectionError`, `RuntimeError`, or custom errors), the client must allow it to propagate unchanged.
2. **No Silent Suppression:** The client must not catch, swallow, or replace fetcher exceptions with partial results.
3. **Determinism:** The client must rely solely on the injected `fetch_page` callable without invoking real network sockets, background threads, or wall-clock timing functions.

