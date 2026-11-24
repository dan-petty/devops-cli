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
from devops_cli.config.settings import get_valkey_password, load_settings
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
    """The credential provider of the Valkey cache tier, resolving the password on connect."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def get_credentials(self) -> tuple[str] | tuple[str, str]:
        pw = get_valkey_password(self._settings)
        return (pw,) if pw else None  # type: ignore[return-value]


def _configured_cache_tier(settings: Settings) -> ValkeyCacheTier:
    """A cache tier over the Valkey that `valkey.url` names.

    A command waits `valkey.timeout`, and a connection waits
    `DEFAULT_VALKEY_CACHE_CONNECT_TIMEOUT_SECONDS`, but never longer than a command. It makes no
    DNS lookup and opens no connection. A `valkey.url` that is not valid raises
    `ConfigurationError`, which names the setting.
    """
    cfg = settings.valkey
    client = ValkeyClient(
        cfg.endpoint,
        credential_provider=_SettingsValkeyCredentialProvider(settings),
        timeout=cfg.timeout,
        connect_timeout=min(cfg.timeout, DEFAULT_VALKEY_CACHE_CONNECT_TIMEOUT_SECONDS),
    )
    return ValkeyCacheTier(client)


_SHARED_TIER_LOCK = threading.Lock()
_shared_tier: ValkeyCacheTier | None = None
_shared_tier_built = False


def shared_cache_tier() -> ValkeyCacheTier | None:
    """The one cache tier of the process, built from the loaded settings on first use.

    When the tier cannot be built, for example because `valkey.url` is not valid or the keyring
    is locked, the process logs one warning and each cache runs with no Valkey tier: this returns
    None until `reset_shared_cache_tier`.
    """
    global _shared_tier, _shared_tier_built
    with _SHARED_TIER_LOCK:
        if not _shared_tier_built:
            try:
                _shared_tier = _configured_cache_tier(load_settings())
            except DevOpsCLIError as exc:
                logger.warning("The Valkey cache is off in this process: %s", exc)
                _shared_tier = None
            _shared_tier_built = True
        return _shared_tier


def install_shared_cache_tier(tier: ValkeyCacheTier | None) -> None:
    """Make `tier` the one cache tier of the process, or turn the Valkey tier off with None.

    A test installs a tier over the in-memory Valkey through this seam; `reset_shared_cache_tier`
    removes it.
    """
    global _shared_tier, _shared_tier_built
    with _SHARED_TIER_LOCK:
        _shared_tier = tier
        _shared_tier_built = True


def reset_shared_cache_tier() -> None:
    """Drop the tier of the process, so the next `shared_cache_tier` builds it again."""
    global _shared_tier, _shared_tier_built
    with _SHARED_TIER_LOCK:
        _shared_tier = None
        _shared_tier_built = False
