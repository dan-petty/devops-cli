"""The Valkey cache tier: an outage turns it off for a cooldown, and a trial turns it on (#2073).

Each test drives the circuit breaker of the tier through the shared Valkey fake, whose server
fails each command while `connected` is False, and through the `clock` fixture, which moves the
wall clock that the breaker reads. No test waits in real time.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest
from fakeredis import FakeServer

from devops_cli.valkey.client import ValkeyClient
from tests.support.fakes.clock import ClockFake

if TYPE_CHECKING:
    from devops_cli.valkey.cache import ValkeyCacheTier

_TIER_LOGGER = "devops_cli.valkey.cache"
_STATE_CHANGE = "The circuit breaker of the Valkey cache tier changed"


def _tier(client: ValkeyClient) -> ValkeyCacheTier:
    """The cache tier over `client`.

    The import is local, so the module loads on a base without the tier.
    """
    from devops_cli.valkey.cache import ValkeyCacheTier

    return ValkeyCacheTier(client)


def _cooldown() -> float:
    """The cooldown of the breaker of the tier, in seconds."""
    from devops_cli.config.defaults import DEFAULT_VALKEY_CACHE_BREAKER_COOLDOWN_SECONDS

    return DEFAULT_VALKEY_CACHE_BREAKER_COOLDOWN_SECONDS


def _changed(old: str, new: str) -> str:
    """The debug record of the tier for one change of the state of its breaker."""
    return f"{_STATE_CHANGE} from {old} to {new}."


def _state_changes(caplog: pytest.LogCaptureFixture) -> list[str]:
    """The records of the tier for the changes of state, in order; not those of failed commands."""
    messages = [record.getMessage() for record in caplog.records if record.name == _TIER_LOGGER]
    return [message for message in messages if message.startswith(_STATE_CHANGE)]


def test_a_valkey_outage_turns_the_cache_tier_off_until_a_trial_after_the_cooldown(
    valkey_server: FakeServer,
    valkey_client: ValkeyClient,
    clock: ClockFake,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Closed, open, the cooldown, half-open and closed again.

    The server holds the value again while the breaker is open, so a read in the cooldown that
    reached Valkey would get it: each such read is a miss, so none reached Valkey.
    """
    valkey_client.set("cached", "value")
    tier = _tier(valkey_client)

    with caplog.at_level(logging.DEBUG, logger=_TIER_LOGGER):
        closed_read = tier.get("cached")
        valkey_server.connected = False
        failed_read = tier.get("cached")
        valkey_server.connected = True
        tier.set("written-in-the-cooldown", "value", ex=60)
        reads_in_the_cooldown = {tier.get("cached") for _ in range(100)}
        clock.shift(_cooldown() - 1)
        last_read_in_the_cooldown = tier.get("cached")
        clock.shift(1)
        trial_read = tier.get("cached")
        tier.set("written-after-the-trial", "value", ex=60)

    assert (
        closed_read,
        failed_read,
        reads_in_the_cooldown,
        last_read_in_the_cooldown,
        trial_read,
    ) == ("value", None, {None}, None, "value")
    assert (
        valkey_client.get("written-in-the-cooldown"),
        valkey_client.get("written-after-the-trial"),
    ) == (None, "value")
    assert _state_changes(caplog) == [
        _changed("closed", "open"),
        _changed("open", "half-open"),
        _changed("half-open", "closed"),
    ]


def test_a_failed_trial_turns_the_cache_tier_off_for_one_more_cooldown(
    valkey_server: FakeServer,
    valkey_client: ValkeyClient,
    clock: ClockFake,
    caplog: pytest.LogCaptureFixture,
) -> None:
    valkey_client.set("cached", "value")
    tier = _tier(valkey_client)

    with caplog.at_level(logging.DEBUG, logger=_TIER_LOGGER):
        valkey_server.connected = False
        tier.get("cached")
        clock.shift(_cooldown())
        failed_trial = tier.get("cached")
        valkey_server.connected = True
        clock.shift(_cooldown() - 1)
        read_in_the_second_cooldown = tier.get("cached")
        clock.shift(1)
        second_trial = tier.get("cached")

    assert (failed_trial, read_in_the_second_cooldown, second_trial) == (None, None, "value")
    assert _state_changes(caplog) == [
        _changed("closed", "open"),
        _changed("open", "half-open"),
        _changed("half-open", "open"),
        _changed("open", "half-open"),
        _changed("half-open", "closed"),
    ]


def test_a_reply_error_leaves_the_cache_tier_on(
    valkey_client: ValkeyClient, caplog: pytest.LogCaptureFixture
) -> None:
    """A server that answers with an error is up, so the next read goes to Valkey."""
    valkey_client.execute("RPUSH", "a-list", "item")
    valkey_client.set("cached", "value")
    tier = _tier(valkey_client)

    with caplog.at_level(logging.DEBUG, logger=_TIER_LOGGER):
        wrong_type_read = tier.get("a-list")
        next_read = tier.get("cached")

    assert (wrong_type_read, next_read, _state_changes(caplog)) == (None, "value", [])
