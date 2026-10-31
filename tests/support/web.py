"""Web fixtures for testing HTTP egress and external network calls."""

from __future__ import annotations

import socket
from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from tests.web_fakes import StubWeb

_ORIG_GETADDRINFO = socket.getaddrinfo


def _is_loopback(host: str) -> bool:
    import ipaddress

    try:
        ip = ipaddress.ip_address(host)
        return ip.is_loopback
    except ValueError:
        return host.lower() in ("localhost", "localhost.localdomain")


def _is_numeric_host(host: Any, resolve: Callable[..., Any] = _ORIG_GETADDRINFO) -> bool:
    """Report whether a host is numeric in any spelling glibc accepts, which needs no DNS query."""
    try:
        resolve(host, None, flags=socket.AI_NUMERICHOST)
    except OSError, UnicodeError:
        return False
    return True


@pytest.fixture
def public_dns(monkeypatch: pytest.MonkeyPatch) -> str:
    """Resolve every external hostname to one public address, for tests that validate egress."""
    address = "93.184.215.14"
    guarded = socket.getaddrinfo

    def resolve(host, port, *args, **kwargs):
        name = host.decode() if isinstance(host, bytes) else str(host)
        flags = kwargs.get("flags", args[2] if len(args) >= 3 else 0) or 0
        if (
            host is None
            or bool(flags & socket.AI_NUMERICHOST)
            or _is_loopback(name)
            or _is_numeric_host(host, _ORIG_GETADDRINFO)
        ):
            return guarded(host, port, *args, **kwargs)
        number = int(port) if isinstance(port, int) or str(port or "").isdigit() else 0
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                (address, number),
            )
        ]

    monkeypatch.setattr(socket, "getaddrinfo", resolve)
    return address


@pytest.fixture
def stub_web(monkeypatch: pytest.MonkeyPatch, public_dns: str) -> Iterator[StubWeb]:
    """Answer every httpx2 client from canned pages, so a fetch never leaves the process."""
    import httpx2

    from devops_cli.http import broker
    from tests.web_fakes import StubWeb, egress_level_of, install_async_client_fake

    web = StubWeb()

    def stub_transport(factory_transport: Any) -> httpx2.MockTransport:
        return httpx2.MockTransport(web.vetting_handler(egress_level_of(factory_transport)))

    class StubClient(httpx2.Client):
        def __init__(self, **kwargs: Any) -> None:
            transport = stub_transport(kwargs.get("transport"))
            super().__init__(**{**kwargs, "transport": transport})

    class StubAsyncClient(httpx2.AsyncClient):
        fake_owner = "stub_web"

        def __init__(self, **kwargs: Any) -> None:
            transport = stub_transport(kwargs.get("transport"))
            super().__init__(**{**kwargs, "transport": transport})

    install_async_client_fake(monkeypatch, StubAsyncClient)
    monkeypatch.setattr(httpx2, "Client", StubClient)
    stub_broker = broker.HttpClientBroker()
    monkeypatch.setattr(broker, "DEFAULT_HTTP_BROKER", stub_broker)
    try:
        yield web
    finally:
        stub_broker.close()
