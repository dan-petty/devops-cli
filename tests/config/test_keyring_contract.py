"""The keyring edge's contract suite (#1318): the keyring seam reads the same answers from
`FakeKeyring` as from `SystemKeyring`.

The Secret Service cases run on both edges where the real one needs no program: the session-bus
check against a socket that this test binds, or a path where nothing listens, and the lock check
where no session-bus address is set, which `secretstorage` refuses before it connects. The entry
cases (write, read, delete, a locked collection, no usable backend) run on the fake. Its answers
follow keyring 25.7.0's Secret Service backend, cited in `tests/support/fakes/keyring.py`. A real
Secret Service needs gnome-keyring-daemon on a D-Bus session bus, and a test starts no system
program (owner rule of 2026-10-24 on #1318), so the real side of those cases does not run.
"""

from __future__ import annotations

import socket
from pathlib import Path

import keyring
import pytest
from keyring.backends.fail import Keyring as FailKeyring
from keyring.errors import KeyringError, NoKeyringError

from devops_cli.config import os_keyring
from devops_cli.config.os_keyring import (
    KeyringEdge,
    KeyringLockedError,
    KeyringUnavailableError,
    SecretStorageError,
    SystemKeyring,
)
from tests.support.fakes.keyring import FakeKeyring

# --- Secret Service answers: the fake and the real edge agree ------------------------------------


def _fake_with_bus(running: bool) -> KeyringEdge:
    fake = FakeKeyring()
    fake.bus_running = running
    return fake


def test_a_bus_that_answers_is_running_on_both_edges(tmp_path: Path) -> None:
    socket_path = tmp_path / "bus"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
        listener.bind(str(socket_path))
        listener.listen(1)
        answers = [
            edge.session_bus_running(socket_path)
            for edge in (_fake_with_bus(True), SystemKeyring())
        ]

    assert answers == [True, True]


@pytest.mark.unreachable("bus")
def test_a_bus_that_nobody_answers_is_not_running_on_both_edges(tmp_path: Path) -> None:
    socket_path = tmp_path / "bus"

    answers = [
        edge.session_bus_running(socket_path) for edge in (_fake_with_bus(False), SystemKeyring())
    ]

    assert answers == [False, False]


def test_without_a_session_bus_the_lock_state_is_unknown_on_both_edges(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DBUS_SESSION_BUS_ADDRESS", raising=False)
    fake = FakeKeyring()
    fake.lock_answers = [None]

    assert [edge.default_collection_locked() for edge in (fake, SystemKeyring())] == [None, None]


def test_the_real_edge_hands_the_seam_the_backend_keyring_selected() -> None:
    assert SystemKeyring().backend() is keyring.get_keyring()


# --- Entries through the seam -------------------------------------------------------------------


def test_a_written_entry_reads_back(keyring_store: FakeKeyring) -> None:
    os_keyring.keyring_write("token", "value-0001")

    assert (
        os_keyring.keyring_read("token"),
        os_keyring.get_keyring_secret("token"),
        os_keyring.has_keyring_secret("token"),
    ) == ("value-0001", "value-0001", True)


def test_a_missing_entry_reads_as_nothing(keyring_store: FakeKeyring) -> None:
    assert (
        os_keyring.keyring_read("absent"),
        os_keyring.get_keyring_secret("absent"),
        os_keyring.has_keyring_secret("absent"),
    ) == (None, None, False)


def test_a_deleted_entry_reads_as_nothing_and_a_second_delete_finds_none(
    keyring_store: FakeKeyring,
) -> None:
    os_keyring.keyring_write("token", "value-0001")

    deleted = (os_keyring.keyring_delete("token"), os_keyring.keyring_delete("token"))

    assert (deleted, os_keyring.keyring_read("token")) == ((True, False), None)


def test_a_locked_keyring_refuses_each_strict_call_and_names_the_unlock_command(
    keyring_store: FakeKeyring,
) -> None:
    keyring_store.locked = True
    calls = (
        lambda: os_keyring.keyring_read("token"),
        lambda: os_keyring.keyring_write("token", "value"),
        lambda: os_keyring.keyring_delete("token"),
        os_keyring.require_persistent_keyring,
    )
    refusals: list[tuple[type[Exception], bool]] = []
    for call in calls:
        with pytest.raises(SecretStorageError) as caught:
            call()
        refusals.append(
            (type(caught.value), "devops devcontainer unlock-keyring" in str(caught.value))
        )

    assert (refusals, os_keyring.get_keyring_secret("token")) == (
        [(KeyringLockedError, True)] * 4,
        None,
    )


def test_with_no_usable_backend_secrets_stay_in_memory_and_persistence_is_refused(
    keyring_store: FakeKeyring, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DEVOPS_CLI_HEADLESS_AUTH", raising=False)
    keyring_store.selected = FailKeyring()

    os_keyring.store_keyring_secret("token", "value-0001")
    with pytest.raises(KeyringUnavailableError) as refused:
        os_keyring.require_persistent_keyring()

    assert (
        os_keyring.has_encrypted_backend(),
        os_keyring.get_keyring_secret("token"),
        "keyring.backends.fail.Keyring" in str(refused.value),
        keyring_store.writes,
    ) == (False, "value-0001", True, {})


def test_headless_auth_refuses_persistence(
    keyring_store: FakeKeyring, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEVOPS_CLI_HEADLESS_AUTH", "true")

    with pytest.raises(KeyringUnavailableError, match="DEVOPS_CLI_HEADLESS_AUTH"):
        os_keyring.require_persistent_keyring()


def test_the_selected_backend_is_named(keyring_store: FakeKeyring) -> None:
    info = os_keyring.backend_info()

    assert (info.name, info.qualified_name, info.priority) == (
        "FakeKeyring",
        "tests.support.fakes.keyring.FakeKeyring",
        1,
    )


def test_the_seam_asks_the_installed_edge_about_the_bus_and_the_lock(
    keyring_store: FakeKeyring, tmp_path: Path
) -> None:
    keyring_store.bus_running = False
    keyring_store.lock_answers = [True]

    answers = (
        os_keyring.session_bus_running(tmp_path / "bus"),
        os_keyring.default_collection_locked(),
    )

    assert (answers, keyring_store.bus_checks) == ((False, True), [tmp_path / "bus"])


class _FailingBackend:
    """A selected backend whose every call raises `error`."""

    priority = 1

    def __init__(self, error: Exception) -> None:
        self.error = error

    def get_password(self, service: str, username: str) -> str | None:
        raise self.error

    def set_password(self, service: str, username: str, password: str) -> None:
        raise self.error

    def delete_password(self, service: str, username: str) -> None:
        raise self.error


def test_a_keyring_that_cannot_answer_reads_as_missing_and_refuses_each_write(
    keyring_store: FakeKeyring, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DEVOPS_CLI_HEADLESS_AUTH", raising=False)
    keyring_store.selected = _FailingBackend(KeyringError("broken"))
    refusals: list[type[Exception]] = []
    for call in (
        lambda: os_keyring.store_keyring_secret("token", "value"),
        lambda: os_keyring.keyring_delete("token"),
    ):
        with pytest.raises(SecretStorageError) as caught:
            call()
        refusals.append(type(caught.value))

    assert (
        os_keyring.get_keyring_secret("token"),
        os_keyring.has_keyring_secret("token"),
        os_keyring.set_keyring_secret("token", "value"),
        refusals,
    ) == (None, False, False, [SecretStorageError, SecretStorageError])


def test_a_backend_with_no_keyring_keeps_a_stored_secret_in_memory(
    keyring_store: FakeKeyring, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DEVOPS_CLI_HEADLESS_AUTH", raising=False)
    keyring_store.selected = _FailingBackend(NoKeyringError())

    before = os_keyring.get_keyring_secret("token")
    os_keyring.store_keyring_secret("token", "value-0001")

    assert (before, os_keyring.get_keyring_secret("token")) == (None, "value-0001")


def test_with_no_usable_backend_nothing_is_read_from_the_keyring(
    keyring_store: FakeKeyring,
) -> None:
    keyring_store.selected = FailKeyring()

    assert (
        os_keyring.get_keyring_secret("token"),
        os_keyring.has_keyring_secret("token"),
        keyring_store.reads,
    ) == (None, False, [])


def test_a_defect_in_the_backend_is_not_read_as_a_missing_secret(
    keyring_store: FakeKeyring,
) -> None:
    keyring_store.selected = _FailingBackend(RuntimeError("defect"))

    with pytest.raises(RuntimeError, match="defect"):
        os_keyring.get_keyring_secret("token")
