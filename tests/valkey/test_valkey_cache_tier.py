"""The Valkey cache tier: an outage turns it off for a cooldown, and a trial turns it on (#2073).

Each test drives the circuit breaker of the tier through the shared Valkey fake, whose server
fails each command while `connected` is False, and through the `clock` fixture, which moves the
wall clock that the breaker reads. No test waits in real time, except the test of a silent host,
which waits one `valkey.timeout` of 0.05 s. The hash, TTL, rename and WATCH commands of the
shared tier of the project brain (#4668) go through the same breaker.
"""

from __future__ import annotations

import logging
import zlib
from typing import TYPE_CHECKING

import pytest
from fakeredis import FakeServer, FakeValkey

from devops_cli.valkey.client import ValkeyClient
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.otlp import FakeCollector
from tests.support.fakes.valkey import SilentValkey, valkey_client_on
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS, wait_until

if TYPE_CHECKING:
    from pathlib import Path

    from devops_cli.valkey.cache import ValkeyCacheTier

_TIER_LOGGER = "devops_cli.valkey.cache"
# The window of a wait that checks that the listener accepts no second connection.
_QUIET_SECONDS: float = 0.2
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
    from devops_cli.ai.rag.library_store import build_library_vector_store
    from devops_cli.security.vulnerability_lookup import CloudflareRadarClient

    store = build_library_vector_store(tmp_path, semantic_needed=False)
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


# ── The commands of the shared tier of the project brain (#4668) ──────────────

# A zlib value, as the shared listing snapshot keeps each record: bytes that are not UTF-8.
_BINARY = zlib.compress(b'{"number": 7, "title": "a record"}' * 8)


def _errors(otlp: FakeCollector) -> dict[tuple[str, str], float]:
    """The failed commands of the tier, by command and error."""
    from devops_cli.telemetry.instruments import VALKEY_CACHE_ERRORS_TOTAL

    counted: dict[tuple[str, str], float] = {}
    for attributes, value in otlp.points(VALKEY_CACHE_ERRORS_TOTAL.name):
        point = (attributes["op"], attributes["error"])
        counted[point] = counted.get(point, 0) + value
    return counted


def test_the_cache_tier_keeps_a_binary_hash_with_a_ttl(
    valkey_server: FakeServer, valkey_client: ValkeyClient
) -> None:
    """The tier writes and reads bytes that are not UTF-8, sets a TTL, removes a field, renames
    the hash and unlinks it."""
    tier = _tier(valkey_client)
    reader = FakeValkey(server=valkey_server)

    written = tier.hset("hash", {"7": _BINARY, "meta": "text"})
    scanned = tier.hscan("hash", 0, 500)
    expired = tier.expire("hash", 60)
    ttl = reader.ttl("hash")
    removed = tier.hdel("hash", "meta", "missing")
    field = tier.hget("hash", "7")
    renamed = tier.rename("hash", "moved")
    unlinked = tier.unlink("moved", "missing")

    assert (written, scanned, expired, 0 < ttl <= 60, removed, field, renamed, unlinked) == (
        2,
        (0, {"7": _BINARY, "meta": b"text"}),
        True,
        True,
        1,
        _BINARY,
        True,
        1,
    )
    assert reader.exists("hash", "moved") == 0


def test_a_writer_whose_watched_key_changed_writes_nothing(
    valkey_server: FakeServer, valkey_client: ValkeyClient
) -> None:
    """A transaction whose key another client changed after the WATCH writes nothing and is not
    tried again; a transaction with no change writes its commands."""
    other = valkey_client_on(valkey_server)
    tier = _tier(valkey_client)
    other.hset("snapshot", {"meta": "first"})
    seen: list[bytes | None] = []

    def lost(meta: bytes | None) -> list[tuple[str, ...]]:
        seen.append(meta)
        other.hset("snapshot", {"meta": "other"})
        return [("HSET", "snapshot", "meta", "mine")]

    def won(meta: bytes | None) -> list[tuple[str, ...]]:
        seen.append(meta)
        return [("HSET", "snapshot", "meta", "mine"), ("EXPIRE", "snapshot", "60")]

    try:
        lost_write = tier.watch_and_write("snapshot", "meta", lost)
        after_the_lost_write = other.hget("snapshot", "meta")
        refused_write = tier.watch_and_write("snapshot", "meta", lambda meta: [])
        won_write = tier.watch_and_write("snapshot", "meta", won)
        after_the_won_write = other.hget("snapshot", "meta")
    finally:
        other.close()

    assert (
        lost_write,
        after_the_lost_write,
        refused_write,
        won_write,
        after_the_won_write,
        seen,
    ) == (False, b"other", False, True, b"mine", [b"first", b"other"])


@pytest.mark.parametrize(
    "last_command",
    [
        pytest.param("WATCH", id="the-watched-read-fails"),
        pytest.param("HGET", id="the-exec-fails"),
    ],
)
def test_a_valkey_that_goes_away_in_a_watch_transaction_opens_the_breaker(
    valkey_server: FakeServer, otlp: FakeCollector, last_command: str
) -> None:
    """valkey-py gives a `WatchError` for a connection that fails while the client watches a
    key. The tier tells it from a lost race: it counts `error="connection"`, opens the breaker
    and gives None, as for each other command that fails."""

    def go_away(command: tuple[object, ...]) -> None:
        if command[0] == last_command:
            valkey_server.connected = False

    client = valkey_client_on(valkey_server, after_command=go_away)
    tier = _tier(client)
    try:
        written = tier.watch_and_write(
            "snapshot", "meta", lambda meta: [("HSET", "snapshot", "meta", "mine")]
        )
    finally:
        client.close()

    assert (written, tier.is_open, _errors(otlp)) == (
        None,
        True,
        {("watch", "connection"): 1.0},
    )


def test_a_failed_tier_command_counts_its_command_and_error(
    valkey_server: FakeServer, valkey_client: ValkeyClient, otlp: FakeCollector
) -> None:
    """The first failed command counts `connection`; a command that the open breaker does not
    send counts `open`, and the server gets nothing."""
    tier = _tier(valkey_client)
    valkey_server.connected = False
    scanned = tier.hscan("hash", 0, 500)
    valkey_server.connected = True
    written = tier.hset("hash", {"1": _BINARY})

    assert (scanned, written, FakeValkey(server=valkey_server).exists("hash"), _errors(otlp)) == (
        None,
        None,
        0,
        {("hscan", "connection"): 1.0, ("hset", "open"): 1.0},
    )


@pytest.mark.usefixtures("keyring_store")
def test_a_silent_valkey_times_out_and_opens_the_breaker(
    silent_valkey: SilentValkey, monkeypatch: pytest.MonkeyPatch, otlp: FakeCollector
) -> None:
    """T3: a Valkey host that accepts the connection and answers no command costs one timeout.

    The tier waits at most 0.25 s for a connection and `valkey.timeout` for a reply. A fact read
    through the tiered mapping gets the source value; its Valkey read counts `timeout` and opens
    the breaker, and no later command opens a second connection to the host.
    """
    from cachetools import cached
    from pydantic import TypeAdapter

    from devops_cli.config.defaults import DEFAULT_VALKEY_CACHE_CONNECT_TIMEOUT_SECONDS
    from devops_cli.config.settings import reset_settings_cache
    from devops_cli.valkey.cache import shared_cache_tier
    from devops_cli.valkey.tiered import TieredMapping

    monkeypatch.setenv("DEVOPS_CLI_VALKEY_URL", f"valkey://127.0.0.1:{silent_valkey.port}")
    monkeypatch.setenv("DEVOPS_CLI_VALKEY_TIMEOUT", "0.05")
    reset_settings_cache()
    tier = shared_cache_tier()
    assert tier is not None

    @cached(TieredMapping("valkey:brain:v1:fact:test", TypeAdapter(str), ttl=60), key=str)
    def read(name: str) -> str:
        return f"source {name}"

    reads = (read("a"), read("b"))
    # The accept thread of the listener records the connection; wait for it with the bound.
    accepted = wait_until(lambda: silent_valkey.connections >= 1, THREAD_HANDOFF_BOUND_SECONDS)
    # A second connection would wait in the backlog of the listener. This short window checks
    # that the thread accepts none, and opens only once it has accepted the first.
    second = wait_until(lambda: silent_valkey.connections > 1, _QUIET_SECONDS)

    assert (
        tier.client.connect_timeout <= DEFAULT_VALKEY_CACHE_CONNECT_TIMEOUT_SECONDS,
        reads,
        tier.is_open,
        accepted,
        second,
        _errors(otlp),
    ) == (
        True,
        ("source a", "source b"),
        True,
        True,
        False,
        {("get", "timeout"): 1.0, ("get", "open"): 1.0, ("set", "open"): 2.0},
    )
