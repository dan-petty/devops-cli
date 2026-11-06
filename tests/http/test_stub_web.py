"""Tests of the `stub_web` fixture, which answers the httpx2 clients that code builds inline."""

from __future__ import annotations

import httpx2

from tests.web_fakes import StubWeb

_FINAL = "https://example.com/final"


def test_stub_web_leaves_httpx2_clients_subclassable(stub_web: StubWeb) -> None:
    """Code that subclasses httpx2's clients while stub_web is active still builds and answers."""
    stub_web.page(_FINAL, "<h1>Final</h1>")

    class Client(httpx2.Client):
        """A subclass as SDKs declare one, such as openai's default client."""

    class AsyncClient(httpx2.AsyncClient):
        """An async subclass, which is answered by the stub as well."""

    with Client() as client:
        status = client.get(_FINAL).status_code

    assert (status, issubclass(AsyncClient, httpx2.AsyncClient), stub_web.requested) == (
        200,
        True,
        [_FINAL],
    )
