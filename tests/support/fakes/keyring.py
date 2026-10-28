"""The keyring edge's fake (#1318): an encrypted keyring held in memory, with the Secret Service
answers that the devcontainer asks for.

`FakeKeyring` is both a `keyring` backend and a `KeyringEdge`, so the keyring seam
(`devops_cli.config.os_keyring`) reads, writes and deletes through it exactly as it does through
the backend that the `keyring` library selects. The `keyring_store` fixture installs it through
the seam's hook; no test calls `keyring.set_keyring` or patches a `keyring` name.

A locked fake raises `KeyringLocked` from every read, write and delete, and deleting a missing
entry raises `PasswordDeleteError`, as keyring 25.7.0's Secret Service backend does
(`keyring/backends/SecretService.py`: `get_preferred_collection` raises `KeyringLocked` when the
collection stays locked; `delete_password` raises `PasswordDeleteError` when no item matches).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest
from keyring.backend import KeyringBackend
from keyring.errors import KeyringLocked, PasswordDeleteError

from devops_cli.config.constants import CONST_KEYRING_UNLOCK_PROBE_KEY


class FakeKeyring(KeyringBackend):
    """An encrypted keyring backend held in memory, and the keyring edge that selects it.

    - `locked` makes every read, write and delete raise `KeyringLocked`.
    - `selected` is the backend the edge hands the seam: the fake itself, or another backend,
      such as `keyring.backends.fail.Keyring()` for a host with no usable keyring.
    - `bus_running` answers the session-bus check, and `lock_answers` the lock check in order;
      with no answer left, the lock check reports `locked`.
    """

    priority = 1  # type: ignore[assignment]

    def __init__(self, values: dict[str, str] | None = None, *, locked: bool = False) -> None:
        super().__init__()
        self.values = dict(values or {})
        self.locked = locked
        # Any: a test may hand the seam a stand-in backend that is not a `KeyringBackend`.
        self.selected: Any = self
        self.bus_running = True
        self.lock_answers: list[bool | None] = []
        self.reads: list[str] = []
        self.writes: dict[str, str] = {}
        self.bus_checks: list[Path] = []
        self.events: list[str] | None = None

    def get_password(self, service: str, username: str) -> str | None:
        if self.locked:
            raise KeyringLocked("locked")
        self.reads.append(username)
        return self.values.get(username)

    def set_password(self, service: str, username: str, password: str) -> None:
        if self.locked:
            raise KeyringLocked("locked")
        self.writes[username] = password
        self.values[username] = password
        if self.events is not None:
            self.events.append(f"keyring-write {username}")

    def delete_password(self, service: str, username: str) -> None:
        if self.locked:
            raise KeyringLocked("locked")
        if username not in self.values:
            raise PasswordDeleteError(username)
        del self.values[username]

    def backend(self) -> KeyringBackend:
        return cast(KeyringBackend, self.selected)

    def session_bus_running(self, socket_path: Path) -> bool:
        self.bus_checks.append(socket_path)
        return self.bus_running

    def default_collection_locked(self) -> bool | None:
        if self.lock_answers:
            return self.lock_answers.pop(0)
        return self.locked

    def secret_reads(self) -> set[str]:
        """The entries read, without the unlock probe, which reads no secret."""
        return set(self.reads) - {CONST_KEYRING_UNLOCK_PROBE_KEY}


@pytest.fixture
def keyring_store() -> Iterator[FakeKeyring]:
    """Install an empty `FakeKeyring` as the keyring edge for the test, and return it."""
    from devops_cli.config import os_keyring

    previous = os_keyring.get_keyring_edge()
    fake = FakeKeyring()
    os_keyring.set_keyring_edge(fake)
    try:
        yield fake
    finally:
        os_keyring.set_keyring_edge(previous)
        os_keyring.clear_remembered_secrets()
