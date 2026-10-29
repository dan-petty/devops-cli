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
with its other tiers. pybreaker reads the time with `datetime.now`, which the `clock` fixture of
the tests moves.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from pybreaker import (
    CircuitBreaker,
    CircuitBreakerError,
    CircuitBreakerListener,
    CircuitBreakerState,
)

from devops_cli.config.defaults import (
    DEFAULT_VALKEY_CACHE_BREAKER_COOLDOWN_SECONDS,
    DEFAULT_VALKEY_CACHE_BREAKER_FAILURES,
    DEFAULT_VALKEY_CACHE_CONNECT_TIMEOUT_SECONDS,
)
from devops_cli.config.settings import get_valkey_password, load_settings
from devops_cli.exceptions import DevOpsCLIError
from devops_cli.exceptions.valkey import ValkeyCommandError, ValkeyError
from devops_cli.valkey.client import ValkeyClient

if TYPE_CHECKING:
    from devops_cli.config.settings import Settings

logger = logging.getLogger(__name__)


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

    def get(self, key: str) -> str | None:
        """The string at `key`; None for a miss, an open breaker and a read that fails."""
        value: str | None = self._send(self.client.get, key)
        return value

    def set(self, key: str, value: str, *, ex: int) -> None:
        """Keep `value` at `key` for `ex` seconds; no write while the breaker is open."""
        self._send(self.client.set, key, value, ex=ex)

    def _send(self, command: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """The reply to one command through the breaker; None when it is not sent or it fails."""
        try:
            return self._breaker.call(command, *args, **kwargs)
        except CircuitBreakerError:
            return None
        except ValkeyError as exc:
            logger.debug("A command of the Valkey cache tier failed: %s", exc)
            return None


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
        password=get_valkey_password(settings),
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


def reset_shared_cache_tier() -> None:
    """Drop the tier of the process, so the next `shared_cache_tier` builds it again."""
    global _shared_tier, _shared_tier_built
    with _SHARED_TIER_LOCK:
        _shared_tier = None
        _shared_tier_built = False
