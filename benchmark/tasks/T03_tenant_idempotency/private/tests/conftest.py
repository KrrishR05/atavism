"""Test configuration and fixtures for T03 Reservation Service."""

from __future__ import annotations

import pytest


class DeterministicIdFactory:
    """Deterministic sequence generator for reservation identifiers."""

    def __init__(self, prefix: str = "res-") -> None:
        self.prefix = prefix
        self.counter = 0
        self.calls: list[str] = []

    def __call__(self) -> str:
        self.counter += 1
        new_id = f"{self.prefix}{self.counter:04d}"
        self.calls.append(new_id)
        return new_id


@pytest.fixture
def id_factory() -> DeterministicIdFactory:
    return DeterministicIdFactory()

