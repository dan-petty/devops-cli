"""Connect-time egress policy: a client dials only the addresses it checked.

A check that resolves a host name before handing its URL to httpx2 leaves a window. httpx2
resolves the name again when it opens the socket, and a rebinding DNS server can answer
differently the second time. The network backends here sit under httpcore2's connection pool,
which hands them every connection it opens, redirect hops included. They resolve the name once,
classify every answer, and dial only the vetted addresses, as IP literals. TLS still uses the
hostname: httpcore2 takes `server_hostname` from the request's origin, not from the address the
backend dialled.

The address classes come from #897's predicates (`is_non_public_ip`, pydantic-ai's
`is_cloud_metadata_ip` and the metadata names), so this check and every pre-flight check agree.
Cloud metadata addresses are refused at every level. Other link-local addresses, such as the
169.254.1.2 a rootless Podman container reaches its host at, are refused at the public and
loopback levels and allowed at the private level.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable, Iterable
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import anyio
import httpcore2
import httpx2
from pydantic_ai._ssrf import is_cloud_metadata_ip

from devops_cli.core.validation import is_cloud_metadata_name, is_non_public_ip
from devops_cli.exceptions import SSRFBlockedError

if TYPE_CHECKING:
    from devops_cli.config.settings import AIConfig

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address
ConnectFailure = httpcore2.ConnectError | httpcore2.ConnectTimeout


class EgressLevel(StrEnum):
    """Which addresses a client may dial. Cloud metadata addresses are refused at every level."""

    PUBLIC = "public"
    """Globally routable addresses only, for URLs that a page, a model or a person supplies."""

    LOOPBACK = "loopback"
    """Public addresses and this machine's loopback, for a configured service without the flag."""

    PRIVATE = "private"
    """Every address but cloud metadata, for internal infrastructure or with the flag set."""


_LEVEL_ADMITS: dict[EgressLevel, Callable[[IPAddress], bool]] = {
    EgressLevel.PUBLIC: lambda address: not is_non_public_ip(address),
    EgressLevel.LOOPBACK: lambda address: address.is_loopback or not is_non_public_ip(address),
    EgressLevel.PRIVATE: lambda address: True,
}


def configured_level(ai_config: AIConfig | None = None) -> EgressLevel:
    """The level of a client whose URL comes from the user's configuration.

    Loopback, or private when `ai.allow_private_network` is set; DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK
    sets that key. The flag is read when the client is built, from `ai_config` or else from the
    loaded settings, never from the environment directly.
    """
    if ai_config is None:
        from devops_cli.config.settings import load_settings

        ai_config = load_settings().ai
    return EgressLevel.PRIVATE if ai_config.allow_private_network else EgressLevel.LOOPBACK


def _destination(host: str, port: int) -> str:
    """Render a connect target for SSRFBlockedError, which masks its host."""
    return str(httpx2.URL(scheme="tcp", host=host, port=port))


def _refusal(sockaddr: tuple[Any, ...], level: EgressLevel) -> str | None:
    """Why the address in one resolver answer may not be dialled at `level`, or None if it may."""
    address = ipaddress.ip_address(sockaddr[0])
    if getattr(address, "scope_id", None) or any(sockaddr[3:4]):
        return "a scoped IPv6 address"
    if is_cloud_metadata_ip(str(address)):
        return "a cloud metadata address"
    if not _LEVEL_ADMITS[level](address):
        return f"an address the {level} egress level refuses"
    return None


def _refuse_metadata_name(host: str, port: int) -> None:
    """Refuse a cloud metadata service name before any lookup is made for it."""
    if is_cloud_metadata_name(host):
        raise SSRFBlockedError(
            _destination(host, port), reason="the destination is a cloud metadata service"
        )


def _vetted(
    host: str, port: int, answers: Iterable[tuple[Any, ...]], level: EgressLevel
) -> list[str]:
    """The answers' addresses in order, or SSRFBlockedError if any one of them is unsafe.

    One unsafe answer refuses them all: which address a later dial would land on is the
    resolver's choice, so a name that answers metadata at all is never dialled.
    """
    sockaddrs = [answer[4] for answer in answers]
    for sockaddr in sockaddrs:
        if reason := _refusal(sockaddr, level):
            raise SSRFBlockedError(
                _destination(host, port),
                reason=f"the destination is {reason}",
                details={"address": str(sockaddr[0]), "egress_level": str(level)},
            )
    if not sockaddrs:
        raise httpcore2.ConnectError(f"No address found for {host!r}")
    return list(dict.fromkeys(str(ipaddress.ip_address(sockaddr[0])) for sockaddr in sockaddrs))


def vet_addresses(host: str, port: int, level: EgressLevel) -> list[str]:
    """Resolve `host` once and return the addresses a client at `level` may dial, in answer order.

    The resolve-and-check every vetting backend runs, and the one a caller whose dialler is not an
    httpx2 client runs before it dials. Such a caller dials the returned IP literals, never the
    name, so nothing resolves the name a second time. An unsafe answer raises SSRFBlockedError,
    and a failed lookup raises httpcore2.ConnectError, which httpx2 reports as httpx2.ConnectError.
    """
    _refuse_metadata_name(host, port)
    try:
        answers = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (OSError, UnicodeError) as exc:
        raise httpcore2.ConnectError(str(exc)) from exc
    return _vetted(host, port, answers, level)


async def avet_addresses(
    host: str, port: int, level: EgressLevel, timeout: float | None = None
) -> list[str]:
    """`vet_addresses` for async clients: the lookup runs off the event loop, within `timeout`."""
    _refuse_metadata_name(host, port)
    try:
        with anyio.fail_after(timeout):
            answers = await anyio.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except TimeoutError as exc:
        raise httpcore2.ConnectTimeout(f"Lookup of {host!r} timed out") from exc
    except (OSError, UnicodeError) as exc:
        raise httpcore2.ConnectError(str(exc)) from exc
    return _vetted(host, port, answers, level)


class VettingBackend(httpcore2.NetworkBackend):
    """A sync network backend that dials only the addresses `vet_addresses` admits.

    Each vetted address is tried in turn, as `socket.create_connection` tries a name's answers,
    and the last failure is raised. The inner backend only ever receives an IP literal.
    """

    def __init__(self, level: EgressLevel, inner: httpcore2.NetworkBackend | None = None) -> None:
        self.level = level
        self.inner = inner or httpcore2.SyncBackend()

    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[Any] | None = None,
    ) -> httpcore2.NetworkStream:
        failures: list[ConnectFailure] = []
        for address in vet_addresses(host, port, self.level):
            try:
                return self.inner.connect_tcp(
                    address,
                    port,
                    timeout=timeout,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except (httpcore2.ConnectError, httpcore2.ConnectTimeout) as exc:
                failures.append(exc)
        raise failures[-1]

    def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: Iterable[Any] | None = None,
    ) -> httpcore2.NetworkStream:
        return self.inner.connect_unix_socket(path, timeout=timeout, socket_options=socket_options)

    def sleep(self, seconds: float) -> None:
        self.inner.sleep(seconds)


class AsyncVettingBackend(httpcore2.AsyncNetworkBackend):
    """The async `VettingBackend`: anyio resolves the name in a worker thread."""

    def __init__(
        self, level: EgressLevel, inner: httpcore2.AsyncNetworkBackend | None = None
    ) -> None:
        self.level = level
        self.inner = inner or httpcore2.AnyIOBackend()

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[Any] | None = None,
    ) -> httpcore2.AsyncNetworkStream:
        failures: list[ConnectFailure] = []
        for address in await avet_addresses(host, port, self.level, timeout):
            try:
                return await self.inner.connect_tcp(
                    address,
                    port,
                    timeout=timeout,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except (httpcore2.ConnectError, httpcore2.ConnectTimeout) as exc:
                failures.append(exc)
        raise failures[-1]

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: Iterable[Any] | None = None,
    ) -> httpcore2.AsyncNetworkStream:
        return await self.inner.connect_unix_socket(
            path, timeout=timeout, socket_options=socket_options
        )

    async def sleep(self, seconds: float) -> None:
        await self.inner.sleep(seconds)


__all__ = [
    "AsyncVettingBackend",
    "EgressLevel",
    "VettingBackend",
    "avet_addresses",
    "configured_level",
    "vet_addresses",
]
