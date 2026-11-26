"""The Valkey cache tier: the reads and writes of a cache, behind a circuit breaker (#2073).

The embeddings engine, the threat-intel client and the library symbol store keep cache entries in
Valkey through one `ValkeyCacheTier` for each process, `shared_cache_tier()` (#1992). So the
caches share one client, one connection pool and one breaker: while Valkey is down, the process
makes one connection attempt in each cooldown, not one for each cache. The tier waits
`DEFAULT_VALKEY_CACHE_CONNECT_TIMEOUT_SECONDS` for a connection and `valkey.timeout` for a command.
The circuit breaker of pybreaker guards the tier:

- Closed: each read and each write goes to Valkey.
- Open: a command that fails opens the breaker. For the cooldown
  (`DEFAULT_VALKEY_CACHE_BREAKER_COOLDOWN_SECONDS`), the tier sends no command: a read is a miss
  and a write does not occur. Thus an outage costs no connection attempt in the cooldown.
- Half-open: the first command after the cooldown is a trial. pybreaker holds its lock while a
  command runs, so one trial goes to Valkey and the other commands wait for its result.
- A trial that succeeds closes the breaker. A trial that fails opens it for one more cooldown.

A reply error (`ValkeyCommandError`) comes from a server that answers, so it does not open the
breaker. A command that fails is a miss or a write that does not occur, and the cache continues
with its other tiers. Each command that fails, and each command that the open breaker does not
send, adds one to `devops_cli_valkey_cache_errors_total` with the command and the error (#4668).
pybreaker reads the time with `datetime.now`, which the `clock` fixture of the tests moves.

The shared tier of the project brain (#4668) uses the hash, TTL, rename and WATCH commands of the
tier through the same breaker, so the listing snapshots and the tool facts share the cooldown of
the embeddings and the threat-intelligence reads. `unlink_if_expiring` reads the TTL of a key and
removes the key in one Lua script, so a write or an `EXPIRE` that comes first keeps the key
(#6611).

A process has a second tier of the same class, `roadmap_state_tier()`, over `valkey-roadmap`, the
Valkey of the shared state of the roadmap jobs that `roadmap.state.url` names (ADR 0021 section 3,
#7294). It has its own client, its own breaker and its own ACL user, so an outage of one Valkey
does not turn the other tier off. A process with no `roadmap.state.url` has no such tier. The
brain index of the alternatives results (#4676) is its first data: the index reads the watermark
with `hscan`, writes each item with `watch_and_write` and counts its entries with `scan`.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING, Any

import valkey.credentials
from pybreaker import (
    STATE_OPEN,
    CircuitBreaker,
    CircuitBreakerError,
    CircuitBreakerListener,
    CircuitBreakerState,
)

from devops_cli.config.constants import ValkeyCacheError
from devops_cli.config.defaults import (
    DEFAULT_VALKEY_CACHE_BREAKER_COOLDOWN_SECONDS,
    DEFAULT_VALKEY_CACHE_BREAKER_FAILURES,
    DEFAULT_VALKEY_CACHE_CONNECT_TIMEOUT_SECONDS,
)
from devops_cli.config.settings import (
    get_roadmap_state_password,
    get_valkey_password,
    load_settings,
)
from devops_cli.exceptions import DevOpsCLIError
from devops_cli.exceptions.valkey import (
    ValkeyAuthenticationError,
    ValkeyCommandError,
    ValkeyError,
    ValkeyTimeoutError,
)
from devops_cli.telemetry.instruments import VALKEY_CACHE_ERRORS_TOTAL, emit
from devops_cli.valkey.client import ValkeyClient

if TYPE_CHECKING:
    from devops_cli.config.settings import Settings
    from devops_cli.valkey.endpoint import ValkeyEndpoint

logger = logging.getLogger(__name__)

# Removes KEYS[1] when it has a TTL of less than ARGV[1] milliseconds; gives the number removed.
# Valkey runs a script as one step, so no command comes between the PTTL and the UNLINK.
_UNLINK_IF_EXPIRING = (
    "local left = redis.call('PTTL', KEYS[1]) "
    "if left >= 0 and left < tonumber(ARGV[1]) then return redis.call('UNLINK', KEYS[1]) end "
    "return 0"
)


class _StateChangeLog(CircuitBreakerListener):
    """Records each change of the state of a breaker in the debug log."""

    def state_change(
        self,
        cb: CircuitBreaker,
        old_state: CircuitBreakerState | None,
        new_state: CircuitBreakerState,
    ) -> None:
        logger.debug(
            "The circuit breaker of the Valkey cache tier changed from %s to %s.",
            None if old_state is None else old_state.name,
            new_state.name,
        )


class ValkeyCacheTier:
    """The Valkey tier of one cache: reads and writes that fail soft, behind a circuit breaker.

    `client` is the Valkey client that the tier sends its commands to.
    """

    def __init__(self, client: ValkeyClient) -> None:
        self.client = client
        self._breaker = CircuitBreaker(
            fail_max=DEFAULT_VALKEY_CACHE_BREAKER_FAILURES,
            reset_timeout=DEFAULT_VALKEY_CACHE_BREAKER_COOLDOWN_SECONDS,
            exclude=[ValkeyCommandError],
            listeners=[_StateChangeLog()],
            throw_new_error_on_trip=False,
        )

    @property
    def is_open(self) -> bool:
        """Whether the breaker is open: the last command failed, and the cooldown sends none.

        A caller reads it after a command that gave None, to tell a miss from a failure.
        """
        return bool(self._breaker.current_state == STATE_OPEN)

    def get(self, key: str) -> str | None:
        """The string at `key`; None for a miss, an open breaker and a read that fails."""
        value: str | None = self._send("get", self.client.get, key)
        return value

    def get_with_ttl(self, key: str) -> tuple[str | None, int] | None:
        """The string at `key` and the time that its key has left in milliseconds (`PTTL`: -2
        when there is no key, -1 when the key has no TTL), read with `GET` and `PTTL` in one
        round trip with no MULTI/EXEC; None for an open breaker and a read that fails. A failure
        counts with `op` `get`, as a plain read does."""
        replies: list[Any] | None = self._send(
            "get", self.client.pipeline, [("GET", key), ("PTTL", key)]
        )
        if replies is None:
            return None
        value, remaining = replies
        return (None if value is None else str(value)), int(remaining)

    def set(self, key: str, value: str, *, ex: int) -> bool:
        """Keep `value` at `key` for `ex` seconds; False when the write is not sent or fails."""
        return bool(self._send("set", self.client.set, key, value, ex=ex))

    def hget(self, key: str, field: str) -> bytes | None:
        """The bytes of one field of the hash at `key`; None for a miss and a failure."""
        value: bytes | None = self._send("hget", self.client.hget, key, field)
        return value

    def hget_with_ttl(self, key: str, field: str) -> tuple[bytes | None, int] | None:
        """The bytes of one field of the hash at `key` and the time that its key has left in
        milliseconds (see `ValkeyClient.hget_with_ttl`), in one round trip; None for an open
        breaker and a read that fails. A failure counts with `op` `hget`, as a plain read does."""
        held: tuple[bytes | None, int] | None = self._send(
            "hget", self.client.hget_with_ttl, key, field
        )
        return held

    def hset(self, key: str, values: Mapping[str, bytes | str]) -> int | None:
        """Set fields of the hash at `key`: the number of new fields, or None on a failure."""
        written: int | None = self._send("hset", self.client.hset, key, values)
        return written

    def hdel(self, key: str, *fields: str) -> int | None:
        """Remove fields of the hash at `key`: the number removed, or None on a failure."""
        removed: int | None = self._send("hdel", self.client.hdel, key, *fields)
        return removed

    def hscan(self, key: str, cursor: int, count: int) -> tuple[int, dict[str, bytes]] | None:
        """One step of `HSCAN` (see `ValkeyClient.hscan`), or None on a failure."""
        step: tuple[int, dict[str, bytes]] | None = self._send(
            "hscan", self.client.hscan, key, cursor, count
        )
        return step

    def scan(self, cursor: int, match: str, count: int) -> tuple[int, list[str]] | None:
        """One step of `SCAN` over the keys that match the pattern `match`: the next cursor, 0 at
        the end, and the keys of the step; None on a failure. `count` is the number of keys that
        the server is asked to look at."""
        step: tuple[int, list[str]] | None = self._send(
            "scan", self.client.scan, cursor, match, count
        )
        return step

    def expire(self, key: str, seconds: int) -> bool:
        """Expire `key` after `seconds`; False when the key is missing or the command fails."""
        return bool(self._send("expire", self.client.expire, key, seconds))

    def unlink(self, *keys: str) -> int | None:
        """Remove keys: the number removed, or None on a failure."""
        removed: int | None = self._send("unlink", self.client.unlink, *keys)
        return removed

    def unlink_if_expiring(self, key: str, within_ms: int) -> int | None:
        """Remove `key` when it expires in less than `within_ms` milliseconds: the number
        removed, or None on a failure. The server reads the TTL and removes the key in one script,
        so a write or an `EXPIRE` that comes before the script keeps the key. A key with no TTL
        and a missing key stay. A failure counts with `op` `unlink`, as a plain removal does."""
        removed: int | None = self._send(
            "unlink", self.client.eval, _UNLINK_IF_EXPIRING, 1, key, within_ms
        )
        return None if removed is None else int(removed)

    def rename(self, source: str, target: str) -> bool:
        """Move `source` onto `target`; False when the command fails."""
        return bool(self._send("rename", self.client.rename, source, target))

    def watch_and_write(
        self,
        key: str,
        field: str,
        decide: Callable[[bytes | None], Sequence[Sequence[Any]]],
    ) -> bool | None:
        """One WATCH transaction (see `ValkeyClient.watch_and_write`): True when it wrote, False
        when `decide` gave no command or another client changed `key`, None on a failure."""
        written: bool | None = self._send("watch", self.client.watch_and_write, key, field, decide)
        return written

    def _send(self, op: str, command: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """The reply to one command through the breaker; None when it is not sent or it fails.

        `op` names the command in `devops_cli_valkey_cache_errors_total`.
        """
        try:
            return self._breaker.call(command, *args, **kwargs)
        except CircuitBreakerError:
            _count_error(op, ValkeyCacheError.OPEN)
            return None
        except ValkeyError as exc:
            logger.debug("A command of the Valkey cache tier failed: %s", exc)
            _count_error(op, _error_of(exc))
            return None


def _error_of(exc: ValkeyError) -> ValkeyCacheError:
    """The error label of a failed command."""
    if isinstance(exc, ValkeyTimeoutError):
        return ValkeyCacheError.TIMEOUT
    if isinstance(exc, ValkeyAuthenticationError):
        return ValkeyCacheError.AUTH
    if isinstance(exc, ValkeyCommandError):
        return ValkeyCacheError.REPLY
    return ValkeyCacheError.CONNECTION


def _count_error(op: str, error: ValkeyCacheError) -> None:
    """Add one failed or unsent command to `devops_cli_valkey_cache_errors_total`."""
    emit(VALKEY_CACHE_ERRORS_TOTAL, 1, {"op": op, "error": error.value})


class _SettingsValkeyCredentialProvider(valkey.credentials.CredentialProvider):
    """The credential provider of a tier, resolving the user and the password on connect.

    `user` gives the ACL user that the settings name, and `password` gives its password.
    """

    def __init__(self, user: Callable[[], str | None], password: Callable[[], str | None]) -> None:
        self._user = user
        self._password = password

    def get_credentials(self) -> tuple[str] | tuple[str, str]:
        """The password, with the ACL user when the settings name one.

        A password that no source gives returns None, and the connection sends no AUTH, as a
        Valkey that needs no password admits it. An empty user sends the password alone, which
        authenticates the `default` user of a server that keeps it.
        """
        password = self._password()
        if not password:
            return None  # type: ignore[return-value]
        user = self._user()
        return (user, password) if user else (password,)


def _tier_over(
    endpoint: ValkeyEndpoint, credentials: _SettingsValkeyCredentialProvider, timeout: float
) -> ValkeyCacheTier:
    """A tier over the Valkey at `endpoint`.

    A command waits `timeout`, and a connection waits
    `DEFAULT_VALKEY_CACHE_CONNECT_TIMEOUT_SECONDS`, but never longer than a command. It makes no
    DNS lookup and opens no connection.
    """
    client = ValkeyClient(
        endpoint,
        credential_provider=credentials,
        timeout=timeout,
        connect_timeout=min(timeout, DEFAULT_VALKEY_CACHE_CONNECT_TIMEOUT_SECONDS),
    )
    return ValkeyCacheTier(client)


def _configured_cache_tier(settings: Settings) -> ValkeyCacheTier:
    """A cache tier over the Valkey that `valkey.url` names, as the user of `valkey.username`.

    A command waits `valkey.timeout`. A `valkey.url` that is not valid raises
    `ConfigurationError`, which names the setting.
    """
    cfg = settings.valkey
    credentials = _SettingsValkeyCredentialProvider(
        lambda: settings.valkey.username, lambda: get_valkey_password(settings)
    )
    return _tier_over(cfg.endpoint, credentials, cfg.timeout)


def _configured_roadmap_state_tier(settings: Settings) -> ValkeyCacheTier | None:
    """A tier over the Valkey that `roadmap.state.url` names, as the user of
    `roadmap.state.username`; None when the setting names no Valkey.

    A command waits `valkey.timeout`, as a command of the cache tier does. A `roadmap.state.url`
    that is not valid raises `ConfigurationError`, which names the setting.
    """
    endpoint = settings.roadmap.state.endpoint
    if endpoint is None:
        return None
    credentials = _SettingsValkeyCredentialProvider(
        lambda: settings.roadmap.state.username, lambda: get_roadmap_state_password(settings)
    )
    return _tier_over(endpoint, credentials, settings.valkey.timeout)


class _ProcessTier:
    """The one tier of a Valkey in the process: built from the loaded settings on first use, and
    kept until `reset`.

    `build` gives the tier, or None when the settings name no Valkey. When it raises, for example
    because the URL is not valid or the keyring is locked, the process logs one warning that
    starts with `name`, and has no tier until `reset`.
    """

    def __init__(self, name: str, build: Callable[[Settings], ValkeyCacheTier | None]) -> None:
        self._name = name
        self._build = build
        self._lock = threading.Lock()
        self._tier: ValkeyCacheTier | None = None
        self._built = False

    def get(self) -> ValkeyCacheTier | None:
        """The tier, built on the first call."""
        with self._lock:
            if not self._built:
                try:
                    self._tier = self._build(load_settings())
                except DevOpsCLIError as exc:
                    logger.warning("%s is off in this process: %s", self._name, exc)
                    self._tier = None
                self._built = True
            return self._tier

    def install(self, tier: ValkeyCacheTier | None) -> None:
        """Make `tier` the tier of the process, or turn the tier off with None."""
        with self._lock:
            self._tier = tier
            self._built = True

    def reset(self) -> None:
        """Drop the tier, so the next `get` builds it again."""
        with self._lock:
            self._tier = None
            self._built = False


_SHARED_TIER = _ProcessTier("The Valkey cache", _configured_cache_tier)
_ROADMAP_STATE_TIER = _ProcessTier("The roadmap state Valkey", _configured_roadmap_state_tier)


def shared_cache_tier() -> ValkeyCacheTier | None:
    """The one cache tier of the process, built from the loaded settings on first use.

    When the tier cannot be built, for example because `valkey.url` is not valid or the keyring
    is locked, the process logs one warning and each cache runs with no Valkey tier: this returns
    None until `reset_shared_cache_tier`.
    """
    return _SHARED_TIER.get()


def install_shared_cache_tier(tier: ValkeyCacheTier | None) -> None:
    """Make `tier` the one cache tier of the process, or turn the Valkey tier off with None.

    A test installs a tier over the in-memory Valkey through this seam; `reset_shared_cache_tier`
    removes it.
    """
    _SHARED_TIER.install(tier)


def reset_shared_cache_tier() -> None:
    """Drop the tier of the process, so the next `shared_cache_tier` builds it again."""
    _SHARED_TIER.reset()


def roadmap_state_tier() -> ValkeyCacheTier | None:
    """The one tier of the process over `valkey-roadmap`, the Valkey of the shared state of the
    roadmap jobs (ADR 0021 section 3), built from the loaded settings on first use.

    Its client sends the ACL user of `roadmap.state.username` with the password of
    `roadmap.state.password`. A reader fails soft (ADR 0023 section 2). This returns None when
    `roadmap.state.url` names no Valkey, as on a workstation, and the reader then has a miss. It
    also returns None, after one warning, when the tier cannot be built, for example because the
    URL is not valid. While the instance does not answer, the breaker of the tier is open: a
    read is a miss and a write does not occur, with no error.
    """
    return _ROADMAP_STATE_TIER.get()


def install_roadmap_state_tier(tier: ValkeyCacheTier | None) -> None:
    """Make `tier` the tier of the roadmap state of the process, or turn it off with None.

    A test installs a tier over the in-memory Valkey through this seam;
    `reset_roadmap_state_tier` removes it.
    """
    _ROADMAP_STATE_TIER.install(tier)


def reset_roadmap_state_tier() -> None:
    """Drop the tier of the roadmap state, so the next `roadmap_state_tier` builds it again."""
    _ROADMAP_STATE_TIER.reset()
