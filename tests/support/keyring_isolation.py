"""Keep one test's keyring backends out of the next test.

keyring registers every concrete `KeyringBackend` subclass as a candidate backend for the rest
of the process, and picks the highest-priority viable one whenever it next detects a backend.
A fake backend class a test defines, such as a `ChainerBackend` over stand-ins, therefore became
a later test's keyring once that test made keyring detect one, and its writes failed with the
fake's errors.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager


@contextmanager
def keyring_backends_restored() -> Iterator[None]:
    """Unregister the backend classes defined inside the block, and restore the backend keyring
    had chosen before it."""
    import keyring.core
    from keyring.backend import KeyringBackend

    classes = set(KeyringBackend._classes)
    chosen = keyring.core._keyring_backend
    try:
        yield
    finally:
        KeyringBackend._classes.intersection_update(classes)
        keyring.core._keyring_backend = chosen
