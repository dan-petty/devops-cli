"""The DNS resolver seam faked for tests, and the `dns` fixture that installs it (#3752).

`DnsFake` stands in for the real resolver under `vet_addresses` and `avet_addresses`
(`devops_cli.http.egress`). A test maps names to addresses, scripts what a name answers on each
lookup, makes a name time out, or answers every name with one public address. A name the fake does
not know fails with the `socket.gaierror` that the real lookup raises. The fake keeps every lookup
in `lookups`, so a test reads what the code resolved and in which order.

An address literal answers itself, as it does for the real lookup: the fake reads it with
`socket.getaddrinfo` and `AI_NUMERICHOST`, which makes no DNS query. `localhost` answers
`127.0.0.1`, as /etc/hosts does.

The fixture also answers `socket.getaddrinfo` from the same fake. That stdlib fallback serves the
code that still calls `socket.getaddrinfo` itself, until each package routes its lookups through
the seam.
"""

from __future__ import annotations

import socket
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Any

import pytest

from devops_cli.http.egress import AddressInfo, install_resolver, reset_resolver

PUBLIC_ADDRESS = "93.184.215.14"
# The stdlib lookup before any test patches it: it reads address literals without a DNS query.
_STDLIB_GETADDRINFO = socket.getaddrinfo

Answer = str | AddressInfo


@dataclass(frozen=True)
class Lookup:
    """One name that the code under test asked the resolver for."""

    host: str
    port: int


def _port_number(port: Any) -> int:
    """The port as `getaddrinfo` reads it: a number, or a digit string, else none (0)."""
    return int(port) if isinstance(port, int) or str(port or "").isdigit() else 0


def _answer(address: Answer, port: int) -> AddressInfo:
    """One `getaddrinfo` answer for `address`; a full answer passes through unchanged."""
    if not isinstance(address, str):
        return address
    if ":" in address:
        return (
            socket.AF_INET6,
            socket.SOCK_STREAM,
            socket.IPPROTO_TCP,
            "",
            (address, port, 0, 0),
        )
    return (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (address, port))


def _name(host: Any) -> str:
    """The host as one lower-case name without a trailing dot."""
    text = host.decode() if isinstance(host, bytes) else str(host)
    return text.lower().rstrip(".")


class DnsFake:
    """In-memory fake for the resolver seam: names to addresses, with a record of each lookup."""

    def __init__(self) -> None:
        self._script: dict[str, list[Sequence[Answer]]] = {}
        self._counts: dict[str, int] = {}
        self._stalled: set[str] = set()
        self._every_name: str | None = None
        self.lookups: list[Lookup] = []
        self.add("localhost", "127.0.0.1")

    def add(self, name: str, *addresses: Answer) -> None:
        """Answer `name` with `addresses` on every lookup; no address is an empty answer."""
        self.script(name, addresses)

    def script(self, name: str, *answers: Sequence[Answer]) -> None:
        """Answer the nth lookup of `name` with the nth entry of `answers`; the last repeats."""
        self._script[_name(name)] = list(answers)
        self._counts[_name(name)] = 0

    def answer_every_name(self, address: str = PUBLIC_ADDRESS) -> str:
        """Answer each name that is not mapped with one public `address`, as the real DNS would."""
        self._every_name = address
        return address

    def stall(self, name: str) -> None:
        """Make the lookup of `name` run past any timeout."""
        self._stalled.add(_name(name))

    def lookups_of(self, name: str) -> list[Lookup]:
        """The lookups of `name`, in order."""
        return [lookup for lookup in self.lookups if lookup.host == _name(name)]

    def _literal(self, name: str, port: int) -> list[AddressInfo] | None:
        """The answer for an address literal, in any spelling glibc accepts, else None."""
        try:
            return list(
                _STDLIB_GETADDRINFO(
                    name, port, type=socket.SOCK_STREAM, flags=socket.AI_NUMERICHOST
                )
            )
        except OSError, UnicodeError:
            return None

    def resolve(self, host: str, port: int) -> list[AddressInfo]:
        """Look `host` up. A stalled name raises TimeoutError at once: no sync lookup can wait."""
        name = _name(host)
        self.lookups.append(Lookup(name, port))
        if name in self._stalled:
            raise TimeoutError(f"Lookup of {name!r} timed out")
        if (literal := self._literal(name, port)) is not None:
            return literal
        if name in self._script:
            answers = self._script[name]
            index = min(self._counts[name], len(answers) - 1)
            self._counts[name] += 1
            return [_answer(address, port) for address in answers[index]]
        if self._every_name is not None:
            return [_answer(self._every_name, port)]
        raise socket.gaierror(socket.EAI_NONAME, "Name or service not known")

    async def aresolve(
        self, host: str, port: int, timeout: float | None = None
    ) -> list[AddressInfo]:
        """`resolve` for async callers. A stalled name raises TimeoutError at once, whatever
        `timeout` is, so no test waits."""
        return self.resolve(host, port)

    def getaddrinfo(
        self, host: Any, port: Any, family: int = 0, type: int = 0, proto: int = 0, flags: int = 0
    ) -> list[AddressInfo]:
        """The stdlib fallback: `socket.getaddrinfo` answered from this fake, for stream sockets.

        A call with no host or with `AI_NUMERICHOST` reads a literal and makes no lookup, so it
        goes to the stdlib and is not recorded.
        """
        if host is None or flags & socket.AI_NUMERICHOST:
            return list(_STDLIB_GETADDRINFO(host, port, family, type, proto, flags))
        return self.resolve(_name(host), _port_number(port))


@pytest.fixture
def dns(monkeypatch: pytest.MonkeyPatch) -> Iterator[DnsFake]:
    """Install `DnsFake` as the resolver under `vet_addresses` and `avet_addresses`, answer
    `socket.getaddrinfo` from it too, and restore the real resolver at teardown."""
    fake = DnsFake()
    install_resolver(fake)
    monkeypatch.setattr(socket, "getaddrinfo", fake.getaddrinfo)
    try:
        yield fake
    finally:
        reset_resolver()
