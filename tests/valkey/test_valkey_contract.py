"""The contract of the Valkey fake: it answers valkey-py's calls as a Valkey server does (#4557).

Each scenario of `tests/support/valkey_scenarios.py` runs over `FakeValkey` on a fresh
`FakeServer`, and must show what each case writes out.

Covered: `SET NX EX`; `SET EXAT`, `KEEPTTL` and an expiry in the past; `HINCRBY` and its refusal
of a field that holds no integer; `ZADD` with a trim by score and by rank; a valkey-py `Lock`
acquired, refused to a second holder, extended, owned and released, and a `Lock` that another
holder took; a script from `register_script`, which meets `NOSCRIPT` and loads itself; and `EVAL`
through the project's `ValkeyClient`.
"""

from __future__ import annotations

from typing import Any

import pytest
from fakeredis import FakeServer, FakeValkey

from tests.support.valkey_scenarios import (
    FAR_EXPIRY,
    INTRUDER_TOKEN,
    SCENARIOS,
    ValkeyScenario,
)

EXPECTED: dict[str, tuple[Any, ...]] = {
    "set_nx_ex": (True, None, "first", True, 1),
    "set_exat": (True, FAR_EXPIRY, True, FAR_EXPIRY, "second", True, None, 1),
    "hincrby": (
        5,
        3,
        ("ResponseError", "hash value is not an integer"),
        {"count": "3", "text": "x"},
        1,
    ),
    "zadd_and_trim": (4, 2, [("c", 3.0), ("d", 4.0)], 1, 2, ["d", "e"], 1),
    "lock_lifecycle": (True, False, True, True, True, False, 0),
    "lock_lost": (True, False, "LockNotOwnedError", "LockNotOwnedError", INTRUDER_TOKEN, 1),
    "registered_script": (3, 7, [True], "7", 1),
    "eval": (
        [1, "two", 3, None, ["devops-contract:eval:key", "x"]],
        "stored",
        "DONE",
        ("ValkeyCommandError", "devops contract refusal"),
        1,
    ),
}


def _over_fake(scenario: ValkeyScenario, server: FakeServer) -> tuple[Any, ...]:
    client = FakeValkey(server=server, decode_responses=True)
    try:
        return scenario.run(client)
    finally:
        client.close()


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda scenario: scenario.name)
def test_the_fake_answers_each_scenario_as_a_valkey_server(
    scenario: ValkeyScenario, valkey_server: FakeServer
) -> None:
    """Verify the fake shows what a Valkey server shows for each scenario."""
    assert _over_fake(scenario, valkey_server) == EXPECTED[scenario.name]
