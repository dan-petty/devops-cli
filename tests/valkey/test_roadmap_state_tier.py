"""The tier of the roadmap state: one client of `valkey-roadmap` for each process (#7294).

`roadmap_state_tier()` gives a `ValkeyCacheTier` over the Valkey that `roadmap.state.url` names
(ADR 0021 section 3), apart from the cache tier of `valkey.url`. Its client sends the ACL user of
`roadmap.state.username` and the password of `roadmap.state.password`. A reader fails soft (ADR
0023 section 2): with no URL the process has no tier, and while the instance is down a read is a
miss and no error. The tests reach a loopback listener that records the commands
(`serving_valkey`), or a port that refuses each connection (`refusing_port`).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tests.support.fakes.valkey import bulk_reply, serving_valkey

_TIER_LOGGER = "devops_cli.valkey.cache"
# A key of the brain index, in the form of ADR 0022 section 5.
_KEY = "roadmap:v1:brain-item:example/repository:7"
# The passwords that the two tiers of the process authenticate with.
_STATE_PASSWORD = "FAKE-7294-state-value"
_CACHE_PASSWORD = "FAKE-7294-cache-value"

Config = Callable[..., Path]


def _state_tier() -> Any:
    """The tier of the roadmap state of the process.

    The import is local, so the module loads on a base without the accessor.
    """
    from devops_cli.valkey.cache import roadmap_state_tier

    return roadmap_state_tier()


@pytest.mark.usefixtures("keyring_store")
def test_the_roadmap_state_tier_sends_the_user_and_the_password_of_its_settings(
    config: Config, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The client authenticates as the user of `roadmap.state.username` with the password of
    `roadmap.state.password`, and never with the user or the password of the cache Valkey."""
    monkeypatch.setenv("DEVOPS_CLI_ROADMAP_STATE_PASSWORD", _STATE_PASSWORD)
    monkeypatch.setenv("DEVOPS_CLI_VALKEY_PASSWORD", _CACHE_PASSWORD)
    with serving_valkey({"GET": bulk_reply(b"value")}) as (port, received):
        config(
            valkey={"username": "sweep"},
            roadmap={"state": {"url": f"valkey://127.0.0.1:{port}/0", "username": "brain"}},
        )
        tier = _state_tier()
        value = tier.get(_KEY)
        tier.client.close()

    assert (value, received) == ("value", [["AUTH", "brain", _STATE_PASSWORD], ["GET", _KEY]])


@pytest.mark.usefixtures("keyring_store")
def test_the_roadmap_state_tier_is_apart_from_the_cache_tier(config: Config) -> None:
    """One process holds two tiers: the cache tier dials `valkey.url`, and the tier of the
    roadmap state dials `roadmap.state.url`. Each call gives the same tier of its kind."""
    from devops_cli.valkey.cache import shared_cache_tier

    config(
        valkey={"url": "valkey://cache.example.com:6379/0"},
        roadmap={"state": {"url": "valkey://state.example.com:6380/1"}},
    )
    state, cache = _state_tier(), shared_cache_tier()
    assert cache is not None

    assert (
        (state.client.host, state.client.port, state.client.db),
        (cache.client.host, cache.client.port, cache.client.db),
        _state_tier() is state,
        state is cache,
    ) == (("state.example.com", 6380, 1), ("cache.example.com", 6379, 0), True, False)


@pytest.mark.usefixtures("keyring_store")
def test_a_read_is_a_miss_while_the_roadmap_state_instance_is_down(
    config: Config, refusing_port: int
) -> None:
    """The instance refuses the connection: a read gives a miss and a write does not occur, with
    no error. The breaker is then open, so the next read is a miss with no second connection."""
    config(roadmap={"state": {"url": f"valkey://127.0.0.1:{refusing_port}/0", "username": "agent"}})
    tier = _state_tier()

    first, opened = tier.get(_KEY), tier.is_open
    assert (first, opened, tier.hget(_KEY, "verdict"), tier.set(_KEY, "value", ex=60)) == (
        None,
        True,
        None,
        False,
    )


@pytest.mark.usefixtures("keyring_store")
def test_a_process_with_no_roadmap_state_url_has_no_tier(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A workstation names no `roadmap.state.url`: the process has no tier of the roadmap state,
    with no error and no warning, so each reader has a miss."""
    with caplog.at_level(logging.WARNING, logger=_TIER_LOGGER):
        tiers = (_state_tier(), _state_tier())

    assert (tiers, [record.getMessage() for record in caplog.records]) == ((None, None), [])


@pytest.mark.usefixtures("keyring_store")
def test_a_roadmap_state_url_that_is_not_valid_gives_no_tier_and_one_warning(
    config: Config, caplog: pytest.LogCaptureFixture
) -> None:
    """The process logs one warning that names the setting, and each reader has a miss."""
    config(roadmap={"state": {"url": "valkey://example.com:99999"}})
    with caplog.at_level(logging.WARNING, logger=_TIER_LOGGER):
        tiers = (_state_tier(), _state_tier())
    warnings = [
        record.getMessage()
        for record in caplog.records
        if record.name == _TIER_LOGGER and record.levelno == logging.WARNING
    ]

    assert (tiers, len(warnings), "roadmap.state.url" in (warnings or [""])[0]) == (
        (None, None),
        1,
        True,
    )
