"""The contract of the Valkey fake: it answers valkey-py's calls as a Valkey server does (#4557).

Each scenario of `tests/support/valkey_scenarios.py` runs twice: once over `FakeValkey` on a fresh
`FakeServer`, and once through a real valkey-py client over the replies of a real `valkey-server`,
recorded in `tests/fixtures/valkey/recorded_exchanges.json`. `RecordedValkey` replays them in
order on a loopback port that the test binds, offline, and fails a command that the record does
not hold. Both runs must show what each case writes out; where they differ, the fake is wrong.

Covered: `SET NX EX`; `SET EXAT`, `KEEPTTL` and an expiry in the past; `HINCRBY` and its refusal
of a field that holds no integer; `ZADD` with a trim by score and by rank; a valkey-py `Lock`
acquired, refused to a second holder, extended, owned and released, and a `Lock` that another
holder took; a script from `register_script`, which meets `NOSCRIPT` and loads itself; and `EVAL`
through the project's `ValkeyClient`.

Not recorded: the moving window of `limits`, which #4563 adds with the `limits` dependency; RESP3;
a server that fails or stops in the middle of a session.
"""

from __future__ import annotations

from typing import Any

import pytest
import valkey
from fakeredis import FakeServer, FakeValkey

from tests.support.valkey_replay import RecordedValkey, load_record, scenario_exchanges
from tests.support.valkey_scenarios import (
    FAR_EXPIRY,
    INTRUDER_TOKEN,
    SCENARIOS,
    ValkeyScenario,
)

# How long the client over the record waits for a reply; the replay answers at once.
REPLY_SECONDS = 5.0

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


def _over_recording(scenario: ValkeyScenario) -> tuple[tuple[Any, ...], list[str], int]:
    with RecordedValkey(scenario_exchanges(scenario.name)) as server:
        client = valkey.Valkey(
            host="127.0.0.1", port=server.port, decode_responses=True, socket_timeout=REPLY_SECONDS
        )
        try:
            seen = scenario.run(client)
        finally:
            client.close()
    return seen, server.unexpected, server.remaining


def test_the_record_is_of_the_locked_valkey_py() -> None:
    """Verify the recorded exchanges are those of the valkey-py that `uv.lock` installs."""
    assert (load_record()["valkey_py"], sorted(load_record()["scenarios"])) == (
        valkey.__version__,
        sorted(scenario.name for scenario in SCENARIOS),
    )


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda scenario: scenario.name)
def test_the_fake_answers_each_scenario_as_the_recorded_server(
    scenario: ValkeyScenario, valkey_server: FakeServer
) -> None:
    """Verify the fake and valkey-py over the recorded server show the same, with no stray command."""
    assert (_over_fake(scenario, valkey_server), *_over_recording(scenario)) == (
        EXPECTED[scenario.name],
        EXPECTED[scenario.name],
        [],
        0,
    )
