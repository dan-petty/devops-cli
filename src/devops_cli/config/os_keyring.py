"""The OS keyring seam: the one module that reaches the keyring and the Secret Service (#1318).

`KeyringEdge` names what devops-cli asks of the system: the keyring backend that the `keyring`
library selected, whether a D-Bus daemon answers on the session-bus socket, and whether the
default Secret Service collection is locked. `SystemKeyring` is the real edge. Every read, write,
delete and backend check below goes through the active edge, which `set_keyring_edge` replaces
and `reset_keyring_edge` restores.

The headless store keeps secrets in memory for a process that has no encrypted keyring: `devops
config auth-headless` and `DEVOPS_CLI_HEADLESS_AUTH` put them there, and `get_keyring_secret`
looks there first.
"""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from devops_cli.config.constants import CONST_KEYRING_SERVICE as KEYRING_SERVICE
from devops_cli.config.constants import CONST_KEYRING_UNLOCK_PROBE_KEY

if TYPE_CHECKING:
    from keyring.backend import KeyringBackend

logger = logging.getLogger(__name__)


class SecretStorageError(RuntimeError):
    """Raised when a secret cannot be stored in the configured keyring backend."""


class KeyringLockedError(SecretStorageError):
    """Raised when the keyring exists but is locked, so nothing can be stored until unlocked."""


class KeyringUnavailableError(SecretStorageError):
    """Raised when secrets would land in no persistent, encrypted keyring.

    That is no backend, an unencrypted one, or the in-memory store `DEVOPS_CLI_HEADLESS_AUTH`
    selects, which loses every value when the process exits.
    """


_KEYRING_LOCKED_HINT = "the OS keyring is locked; run `devops devcontainer unlock-keyring`"


class KeyringEdge(Protocol):
    """What devops-cli asks of the OS keyring and of the Secret Service behind it."""

    def backend(self) -> KeyringBackend:
        """The keyring backend that reads, writes and deletes entries."""

    def session_bus_running(self, socket_path: Path) -> bool:
        """Whether a D-Bus daemon accepts connections on the session-bus socket."""

    def default_collection_locked(self) -> bool | None:
        """Whether the default Secret Service collection is locked; None if it is missing."""


class SystemKeyring:
    """The real edge: the `keyring` library's selected backend, a socket and `secretstorage`."""

    def backend(self) -> KeyringBackend:
        import keyring

        return keyring.get_keyring()

    def session_bus_running(self, socket_path: Path) -> bool:
        import socket

        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.2)
            try:
                sock.connect(str(socket_path))
            except OSError:
                return False
        return True

    def default_collection_locked(self) -> bool | None:
        import contextlib

        import secretstorage

        try:
            with contextlib.closing(secretstorage.dbus_init()) as connection:
                return bool(secretstorage.get_default_collection(connection).is_locked())
        except secretstorage.exceptions.SecretStorageException:
            return None


_EDGE: KeyringEdge | None = None
_EDGE_LOCK = threading.Lock()
_HEADLESS_SECRETS: dict[str, str] = {}


def get_keyring_edge() -> KeyringEdge:
    """The active keyring edge: the one `set_keyring_edge` installed, else `SystemKeyring`."""
    with _EDGE_LOCK:
        return _EDGE if _EDGE is not None else SystemKeyring()


def set_keyring_edge(edge: KeyringEdge | None) -> None:
    """Install the keyring edge that every operation of this module uses."""
    global _EDGE
    with _EDGE_LOCK:
        _EDGE = edge


def reset_keyring_edge() -> None:
    """Restore `SystemKeyring` as the keyring edge."""
    set_keyring_edge(None)


@dataclass(frozen=True)
class KeyringBackendInfo:
    """The selected keyring backend, as `devops config audit-keys` and errors name it."""

    name: str
    qualified_name: str
    priority: float


def backend_info() -> KeyringBackendInfo:
    """Name the keyring backend that the active edge selected."""
    backend = get_keyring_edge().backend()
    backend_type = type(backend)
    return KeyringBackendInfo(
        name=backend_type.__name__,
        qualified_name=f"{backend_type.__module__}.{backend_type.__qualname__}",
        priority=getattr(backend, "priority", 0),
    )


def _is_unencrypted_backend(backend: object) -> bool:
    """Report whether a backend keeps secrets in plain text."""
    return "Plaintext" in type(backend).__name__ or "keyrings.alt" in type(backend).__module__


def has_encrypted_backend() -> bool:
    """Report whether the selected backend is usable and keeps every secret encrypted."""
    from keyring.backends.chainer import ChainerBackend
    from keyring.backends.fail import Keyring as FailKeyring

    backend = get_keyring_edge().backend()
    if isinstance(backend, FailKeyring):
        return False

    # keyring picks the chainer whenever several backends are viable, and the chainer falls
    # through to the next one when a write fails -- a locked Secret Service would hand the
    # secret to any plaintext backend behind it. Every backend it chains must be encrypted.
    members = list(backend.backends) if isinstance(backend, ChainerBackend) else [backend]
    if not members or any(_is_unencrypted_backend(member) for member in members):
        return False

    priority = getattr(backend, "priority", 0)
    return bool(priority > 0)


def _backend_errors() -> tuple[type[Exception], ...]:
    """The errors of a keyring that cannot answer: `keyring`'s own, and on Linux the Secret
    Service's, which keyring's Secret Service backend passes through when the session bus fails
    (`get_preferred_collection` calls `secretstorage.dbus_init()` outside its `try`)."""
    from keyring.errors import KeyringError

    try:
        from secretstorage.exceptions import SecretStorageException
    except ImportError:
        return (KeyringError,)
    return (KeyringError, SecretStorageException)


def headless_auth_enabled() -> bool:
    """Report whether `DEVOPS_CLI_HEADLESS_AUTH` keeps secrets in the in-memory store."""
    return os.environ.get("DEVOPS_CLI_HEADLESS_AUTH", "").lower() in ("true", "1", "yes")


def remember_secret(key: str, value: str) -> None:
    """Keep a secret in the in-memory store for this process only."""
    _HEADLESS_SECRETS[key] = value


def clear_remembered_secrets() -> None:
    """Empty the in-memory store."""
    _HEADLESS_SECRETS.clear()


def get_keyring_secret(key: str) -> str | None:
    """Read a secret from the in-memory store, else the keyring; None when it cannot be read."""
    from keyring.errors import KeyringLocked, NoKeyringError

    if key in _HEADLESS_SECRETS:
        return _HEADLESS_SECRETS[key]

    if not has_encrypted_backend():
        return None

    try:
        return get_keyring_edge().backend().get_password(KEYRING_SERVICE, key)
    except NoKeyringError:
        return None
    except KeyringLocked:
        logger.warning("Cannot read a secret: %s", _KEYRING_LOCKED_HINT)
        return None
    except _backend_errors() as exc:
        logger.warning("Failed to retrieve secret from OS Keyring: %s", type(exc).__name__)
        return None


def has_keyring_secret(key: str) -> bool:
    """Check whether a secret key exists in the in-memory store or the keyring."""
    from keyring.errors import KeyringLocked

    if key in _HEADLESS_SECRETS:
        return True

    if not has_encrypted_backend():
        return False

    try:
        value = get_keyring_edge().backend().get_password(KEYRING_SERVICE, key)
        return bool(value is not None)
    except KeyringLocked:
        logger.warning("Cannot check for a secret: %s", _KEYRING_LOCKED_HINT)
        return False
    except _backend_errors() as exc:
        logger.debug("Keyring check failed: %s", type(exc).__name__)
        return False


def store_keyring_secret(key: str, value: str) -> None:
    """Store a secret in the keyring, or in memory when headless or no backend is usable.

    A locked keyring raises `KeyringLockedError`, and any other failure `SecretStorageError`.
    """
    from keyring.errors import KeyringLocked, NoKeyringError

    if headless_auth_enabled() or not has_encrypted_backend():
        remember_secret(key, value)
        return

    try:
        get_keyring_edge().backend().set_password(KEYRING_SERVICE, key, value)
    except NoKeyringError:
        remember_secret(key, value)
    except KeyringLocked as exc:
        raise KeyringLockedError(f"Cannot store {key}: {_KEYRING_LOCKED_HINT}") from exc
    except Exception as exc:
        raise SecretStorageError(f"Failed to store secret in keyring: {exc}") from exc


def set_keyring_secret(key: str, value: str) -> bool:
    """Store a secret as `store_keyring_secret` does, reporting a failure as False."""
    try:
        store_keyring_secret(key, value)
        return True
    except SecretStorageError as exc:
        logger.warning("Failed to set secret in OS Keyring: %s", type(exc).__name__)
        return False


def require_persistent_keyring() -> None:
    """Raise unless an encrypted OS keyring is in use and unlocked.

    For commands that must never take a locked keyring for a missing entry, nor keep a value
    only in memory: a locked keyring raises `KeyringLockedError`; no encrypted backend, or the
    headless in-memory store, raises `KeyringUnavailableError`. The lock is probed by looking
    up an entry that is never stored, so no secret is read.
    """
    if headless_auth_enabled():
        raise KeyringUnavailableError(
            "DEVOPS_CLI_HEADLESS_AUTH keeps secrets in memory only, so a value stored now would "
            "be lost when the command exits; unset it to use the OS keyring"
        )
    if not has_encrypted_backend():
        raise KeyringUnavailableError(
            f"no encrypted OS keyring backend is available (found {backend_info().qualified_name}); "
            "install and start one, such as gnome-keyring"
        )
    keyring_read(CONST_KEYRING_UNLOCK_PROBE_KEY)


def keyring_read(key: str) -> str | None:
    """Read a keyring entry, raising `KeyringLockedError` instead of returning None when locked."""
    from keyring.errors import KeyringError, KeyringLocked

    try:
        return get_keyring_edge().backend().get_password(KEYRING_SERVICE, key)
    except KeyringLocked as exc:
        raise KeyringLockedError(f"Cannot read {key}: {_KEYRING_LOCKED_HINT}") from exc
    except KeyringError as exc:
        raise SecretStorageError(f"Cannot read {key}: {type(exc).__name__}") from exc


def keyring_write(key: str, value: str) -> None:
    """Store a keyring entry in the OS keyring itself, never in the in-memory store."""
    from keyring.errors import KeyringError, KeyringLocked

    try:
        get_keyring_edge().backend().set_password(KEYRING_SERVICE, key, value)
    except KeyringLocked as exc:
        raise KeyringLockedError(f"Cannot store {key}: {_KEYRING_LOCKED_HINT}") from exc
    except KeyringError as exc:
        raise SecretStorageError(f"Cannot store {key}: {type(exc).__name__}") from exc


def keyring_delete(key: str) -> bool:
    """Delete a keyring entry from the OS keyring itself, returning False when there was none."""
    from keyring.errors import KeyringError, KeyringLocked, PasswordDeleteError

    try:
        get_keyring_edge().backend().delete_password(KEYRING_SERVICE, key)
    except PasswordDeleteError:
        return False
    except KeyringLocked as exc:
        raise KeyringLockedError(f"Cannot delete {key}: {_KEYRING_LOCKED_HINT}") from exc
    except KeyringError as exc:
        raise SecretStorageError(f"Cannot delete {key}: {type(exc).__name__}") from exc
    return True


def session_bus_running(socket_path: Path) -> bool:
    """Check whether a D-Bus daemon accepts connections on the session-bus socket."""
    return get_keyring_edge().session_bus_running(socket_path)


def default_collection_locked() -> bool | None:
    """Report whether the default Secret Service collection is locked; None if it is missing."""
    return get_keyring_edge().default_collection_locked()
