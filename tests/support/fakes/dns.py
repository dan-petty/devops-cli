"""The DNS edge's fake (#3752): a resolver that maps names to addresses, and the `dns` fixture
that installs it.

`FakeResolver` is a `Resolver` of `devops_cli.http.egress`, so `vet_addresses` and
`avet_addresses` resolve through it exactly as they resolve through the system. It answers a name
from its map, scripts the answers of a name per lookup (a name that rebinds), answers every name
with one public address, stalls a name, and fails an unknown name with the `socket.gaierror` that
`socket.getaddrinfo` raises. An IP literal answers itself, as it does in the real lookup. It
records each lookup.

The `dns` fixture installs the fake through the seam's hook and removes it at teardown. Until the
code that calls `socket.getaddrinfo` itself goes through the seam, the fixture also answers
`socket.getaddrinfo` from the same fake, the stdlib fallback that docs/TESTING.md allows.
"""

from __future__ import annotations

import socket
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import pytest

from devops_cli.http import egress

PUBLIC_ADDRESS = "93.184.215.14"
"""The address `answer_every_name` gives, the one `public_dns` gave."""

# `socket.getaddrinfo` as the support module sees it at import: a numeric host needs no query,
# so the flag `AI_NUMERICHOST` makes the real lookup (or the floor's guard) answer it.
_NUMERIC_LOOKUP = socket.getaddrinfo


@dataclass(frozen=True)
class Lookup:
    """One lookup the fake answered: the host and port asked, and the timeout of an async one."""

    host: str
    port: int
    timeout: float | None = None


def _answer(address: str, port: int) -> tuple[Any, ...]:
    """One `getaddrinfo` answer for a stream socket to `address`."""
    if ":" in address:
        return (socket.AF_INET6, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (address, port, 0, 0))
    return (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (address, port))


class FakeResolver:
    """An in-memory resolver. `localhost` answers `127.0.0.1`; every other name must be mapped."""

    def __init__(self) -> None:
        self._scripts: dict[str, list[tuple[str, ...]]] = {"localhost": [("127.0.0.1",)]}
        self._every_name: str | None = None
        self._stalled: set[str] = set()
        self.lookups: list[Lookup] = []

    def map(self, name: str, *addresses: str) -> None:
        """Answer `name` with `addresses`, in order, at every lookup."""
        self.script(name, addresses)

    def script(self, name: str, *per_lookup: Sequence[str]) -> None:
        """Answer the nth lookup of `name` with `per_lookup[n]`; the last entry repeats."""
        self._scripts[name.lower()] = [tuple(addresses) for addresses in per_lookup]

    def answer_every_name(self, address: str = PUBLIC_ADDRESS) -> str:
        """Answer every name that is not mapped with `address`, as `public_dns` did."""
        self._every_name = address
        return address

    def stall(self, name: str) -> None:
        """Make the lookup of `name` outlast any timeout."""
        self._stalled.add(name.lower())

    def lookup(self, host: str, port: int) -> list[tuple[Any, ...]]:
        name = host.lower()
        if name in self._stalled:
            raise RuntimeError(f"a sync lookup of the stalled name {host!r} would never end")
        return self._answer(host, port, None)

    async def alookup(self, host: str, port: int, timeout: float | None) -> list[tuple[Any, ...]]:
        if host.lower() in self._stalled:
            self.lookups.append(Lookup(host, port, timeout))
            raise TimeoutError(f"Lookup of {host!r} stalled")
        return self._answer(host, port, timeout)

    def _answer(self, host: str, port: int, timeout: float | None) -> list[tuple[Any, ...]]:
        name = host.lower()
        earlier = sum(1 for lookup in self.lookups if lookup.host.lower() == name)
        self.lookups.append(Lookup(host, port, timeout))
        if name in self._scripts:
            script = self._scripts[name]
            return [_answer(address, port) for address in script[min(earlier, len(script) - 1)]]
        try:
            return list(
                _NUMERIC_LOOKUP(host, port, type=socket.SOCK_STREAM, flags=socket.AI_NUMERICHOST)
            )
        except OSError, UnicodeError:
            pass
        if self._every_name is not None:
            return [_answer(self._every_name, port)]
        raise socket.gaierror(socket.EAI_NONAME, "Name or service not known")


def _stdlib_lookup(fake: FakeResolver, previous: Any) -> Any:
    """A `socket.getaddrinfo` that answers a name from `fake` and leaves numeric-only calls to
    the lookup it replaces."""

    def getaddrinfo(host: Any, port: Any, *args: Any, **kwargs: Any) -> list[tuple[Any, ...]]:
        flags = kwargs.get("flags", args[3] if len(args) >= 4 else 0) or 0
        if host is None or flags & socket.AI_NUMERICHOST:
            return list(previous(host, port, *args, **kwargs))
        name = host.decode() if isinstance(host, bytes) else str(host)
        number = int(port) if isinstance(port, int) or str(port or "").isdigit() else 0
        return fake.lookup(name, number)

    return getaddrinfo


@contextmanager
def installed_dns() -> Iterator[FakeResolver]:
    """Install a `FakeResolver` as the resolver and as `socket.getaddrinfo`, then restore both."""
    fake = FakeResolver()
    previous_resolver = egress.set_resolver(fake)
    previous_lookup = socket.getaddrinfo
    socket.getaddrinfo = _stdlib_lookup(fake, previous_lookup)
    try:
        yield fake
    finally:
        socket.getaddrinfo = previous_lookup
        egress.set_resolver(previous_resolver)


@pytest.fixture
def dns() -> Iterator[FakeResolver]:
    """Install an empty `FakeResolver` as the DNS resolver for the test, and return it."""
    with installed_dns() as fake:
        yield fake
