# Atavism Task T05: Out-of-Order Event Stream Projection Protocol

## Objective
Implement the `AccountProjector` class in `src/atavism_projection/projector.py` to maintain deterministic account state projections from an asynchronous stream of financial events.

## Requirements
1. Review `contract.md` for domain invariants, validation rules, monetary precision standards, sequence ordering, duplicate handling, and state projection semantics.
2. Implement the `apply_event(event: AccountEvent) -> AccountProjection` and `get_projection(account_id: str) -> AccountProjection | None` methods on `AccountProjector`.
3. Preserve the data models and exceptions defined in `src/atavism_projection/types.py`. Do not modify `types.py`.
4. Ensure all calculations use Python `Decimal` arithmetic with at most two fractional decimal places. Floating-point numbers are strictly prohibited.
5. All domain events must be treated as immutable; do not modify incoming `AccountEvent` instances.

