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
    from pathlib import Path

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


def _caches_of_one_process(tmp_path: Path) -> tuple[object, object, object, object]:
    """The Valkey tiers of two embeddings engines, one Radar client and the `ai ingest` store.

    The imports are local, so the module loads on a base without the shared tier.
    """
    from devops_cli.ai.rag.embeddings import EmbeddingsEngine
    from devops_cli.commands.ai_ingest import _build_runtime_vector_store
    from devops_cli.security.vulnerability_lookup import CloudflareRadarClient

    store = _build_runtime_vector_store(tmp_path, semantic_needed=False)
    return (
        EmbeddingsEngine()._l2,
        EmbeddingsEngine()._l2,
        CloudflareRadarClient()._l2,
        store.symbol_cache,
    )


@pytest.mark.usefixtures("keyring_store")
def test_the_caches_of_one_process_share_one_cache_tier(tmp_path: Path) -> None:
    """Two engines, a Radar client and the library store hold one tier, so one breaker (#1992)."""
    first_engine, second_engine, radar, symbols = _caches_of_one_process(tmp_path)

    assert (
        first_engine is not None,
        second_engine is first_engine,
        radar is first_engine,
        symbols is first_engine,
    ) == (True, True, True, True)


@pytest.mark.usefixtures("keyring_store")
def test_while_valkey_refuses_a_second_cache_dials_nothing_in_the_cooldown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    unexpected_loopback_connects: list[str],
) -> None:
    """The first cache's read dials the refusing Valkey once; the other caches dial nothing.

    A service listens on the configured port through the C socket type, as a port-forward to a
    live Valkey does. The guard refuses each dial and reports it, and the service sees none.
    """
    import _socket
    import socket

    from devops_cli.config.settings import reset_settings_cache

    with socket.socket() as service:
        _socket.socket.bind(service, ("127.0.0.1", 0))
        _socket.socket.listen(service)
        service.setblocking(False)
        port = service.getsockname()[1]
        monkeypatch.setenv("DEVOPS_CLI_VALKEY_URL", f"valkey://127.0.0.1:{port}")
        reset_settings_cache()
        caches = _caches_of_one_process(tmp_path)
        try:
            reads = [cache.get(f"key-{index}") for index, cache in enumerate(caches)]
            dials = list(unexpected_loopback_connects)
        finally:
            unexpected_loopback_connects.clear()

    assert (reads, dials) == ([None] * 4, [f"127.0.0.1:{port} (MainThread)"])


@pytest.mark.usefixtures("keyring_store")
@pytest.mark.parametrize(
    ("valkey_timeout", "expected"),
    [
        pytest.param("2.0", (2.0, "default"), id="the-short-default-under-the-read-timeout"),
        pytest.param("0.05", (0.05, 0.05), id="never-longer-than-the-read-timeout"),
    ],
)
def test_the_shared_tier_waits_a_short_time_for_a_connection(
    monkeypatch: pytest.MonkeyPatch,
    valkey_timeout: str,
    expected: tuple[float, object],
) -> None:
    """A command waits `valkey.timeout`; a connection waits the short default, at most as long."""
    from devops_cli.config.defaults import DEFAULT_VALKEY_CACHE_CONNECT_TIMEOUT_SECONDS
    from devops_cli.config.settings import reset_settings_cache
    from devops_cli.valkey.cache import shared_cache_tier

    monkeypatch.setenv("DEVOPS_CLI_VALKEY_TIMEOUT", valkey_timeout)
    reset_settings_cache()
    tier = shared_cache_tier()
    assert tier is not None
    read, connect = expected
    if connect == "default":
        connect = DEFAULT_VALKEY_CACHE_CONNECT_TIMEOUT_SECONDS

    assert (tier.client.timeout, tier.client.connect_timeout) == (read, connect)


@pytest.mark.usefixtures("keyring_store")
def test_a_valkey_url_that_is_not_valid_turns_each_cache_off_with_one_warning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The caches run with no Valkey tier, and the process logs one warning that names the setting."""
    from devops_cli.config.settings import reset_settings_cache

    monkeypatch.setenv("DEVOPS_CLI_VALKEY_URL", "valkey://example.com:99999")
    reset_settings_cache()
    with caplog.at_level(logging.WARNING, logger=_TIER_LOGGER):
        tiers = _caches_of_one_process(tmp_path)
    warnings = [
        record.getMessage()
        for record in caplog.records
        if record.name == _TIER_LOGGER and record.levelno == logging.WARNING
    ]

    assert (tiers, len(warnings), "valkey.url" in (warnings or [""])[0]) == (
        (None, None, None, None),
        1,
        True,
    )
