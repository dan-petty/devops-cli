"""The intervals of the roadmap Service (#2965): each is a prime number, so no two rows keep the
same poll tick for long and none lands on a multiple of 5 minutes."""

from __future__ import annotations

import pytest

from devops_cli.config import defaults

INTERVALS = sorted(
    name
    for name in vars(defaults)
    if name.startswith(("DEFAULT_ROADMAP_", "DEFAULT_SERVICE_"))
    and name.endswith(("_INTERVAL_MINUTES", "_POLL_INTERVAL_SECONDS"))
)


def _is_prime(number: int) -> bool:
    return number > 1 and all(number % divisor for divisor in range(2, int(number**0.5) + 1))


def test_interval_constants_are_found() -> None:
    assert len(INTERVALS) == 8


@pytest.mark.parametrize("name", INTERVALS)
def test_interval_is_prime(name: str) -> None:
    value = getattr(defaults, name)

    assert _is_prime(value), f"{name} is {value}, which is not a prime number"
    assert value % 5, f"{name} is {value}, a multiple of 5"
