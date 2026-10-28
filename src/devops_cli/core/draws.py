"""Seeded draws that give the same result for the same seed on every host and Python version.

A benchmark sample and a defect corpus must repeat for a seed, and neither draw guards anything.
The order is the SHA-256 of the seed and each item's position, so no pseudo-random generator is
involved and Bandit's B311 has nothing to report (#1538).
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence


def _key(seed: str, position: int) -> bytes:
    return hashlib.sha256(f"{seed}:{position}".encode()).digest()


def seeded_sample[T](items: Sequence[T], k: int, seed: str) -> list[T]:
    """The first `k` of `items` (all of them when `k` is larger) in the order that `seed` gives."""
    order = sorted(range(len(items)), key=lambda position: _key(seed, position))
    return [items[position] for position in order[:k]]


def seeded_choice[T](items: Sequence[T], seed: str) -> T:
    """One of `items`, which must not be empty, by the order that `seed` gives."""
    return seeded_sample(items, 1, seed)[0]
