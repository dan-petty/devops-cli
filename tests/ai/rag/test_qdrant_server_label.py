"""Qdrant log lines and errors name the server by host and port.

The configured URL can hold userinfo, which the client sends as Basic authentication, and a path.
No text that the client writes holds either. An address that is not a URL shows as `unknown`.
"""

from __future__ import annotations

import logging
from typing import Any

import pytest

from devops_cli.ai.rag.investigator import investigate_rag_context
from devops_cli.ai.rag.qdrant import QdrantClient, QdrantClientError
from devops_cli.config.settings import Settings
from devops_cli.exceptions import InvalidURLError
from tests.support.fakes.dns import PUBLIC_ADDRESS, DnsFake
from tests.support.fakes.kubernetes import FakeCluster

pytestmark = pytest.mark.usefixtures("keyring_store")


@pytest.fixture(autouse=True)
def _mock_example_com_dns(dns: DnsFake) -> None:
    dns.add("example.com", PUBLIC_ADDRESS)


_HTTP_URL = "http://user:secret@example.com:6333/prefix/path"
_K8S_URL = "k8s+https://user:secret@devops/qdrant:6333/prefix/path?q=secret"
_SECRETS = ("secret", "user", "prefix", "path", "://")


def _leaks(text: str) -> list[str]:
    return [secret for secret in _SECRETS if secret in text]


@pytest.mark.parametrize(
    ("url", "label"),
    [
        ("http://example.com:6333", "example.com:6333"),
        (_HTTP_URL, "example.com:6333"),
        ("https://token@example.com", "example.com"),
        ("k8s://devops/qdrant:6333", "qdrant.devops:6333"),
        (_K8S_URL, "qdrant.devops:6333"),
        ("k8s://devops/qdrant:http", "qdrant.devops"),
        ("k8s://devops", "unknown"),
        ("user:secret@example.com:6333/prefix", "unknown"),
        ("http://example.com:65535", "example.com:65535"),
        ("http://example.com:65536", "unknown"),
        ("http://example.com:99999", "unknown"),
        ("", "unknown"),
    ],
    ids=[
        "port",
        "userinfo-and-path",
        "user-only-default-port",
        "k8s",
        "k8s-userinfo",
        "k8s-named-port",
        "k8s-malformed",
        "no-scheme",
        "last-valid-port",
        "port-above-range",
        "port-far-above-range",
        "empty",
    ],
)
def test_the_label_names_the_server_by_host_and_port(url: str, label: str) -> None:
    from devops_cli.ai.rag.qdrant import qdrant_server_label

    assert qdrant_server_label(url) == label


@pytest.mark.parametrize("url", [_HTTP_URL, _K8S_URL], ids=["http", "k8s"])
def test_the_client_log_line_of_list_collections_names_the_server_by_host_and_port(
    caplog: pytest.LogCaptureFixture, cluster: FakeCluster, refusing_port: int, url: str
) -> None:
    """A real client dials a loopback port that refuses; the line names the configured server."""
    cluster.configuration.host = f"http://127.0.0.1:{refusing_port}"
    if url == _HTTP_URL:
        url = f"http://user:secret@127.0.0.1:{refusing_port}/prefix/path"
    client = QdrantClient(url, allow_private_network=True, timeout=5.0)

    with caplog.at_level(logging.DEBUG, logger="devops_cli.ai.rag.qdrant"):
        with pytest.raises(QdrantClientError, match="Error connecting to Qdrant"):
            client.list_collections()

    (line,) = (
        record.getMessage()
        for record in caplog.records
        if record.getMessage().startswith("Failed to list Qdrant collections")
    )
    host = f"127.0.0.1:{refusing_port}" if "127.0.0.1" in url else "qdrant.devops:6333"
    assert line.startswith(f"Failed to list Qdrant collections from {host}: ")
    assert _leaks(line) == []


class _FailingGetCollections:
    """A native client whose collection call fails with an exception that holds the URL."""

    def __init__(self, url: str) -> None:
        self.url = url

    def get_collections(self) -> None:
        raise RuntimeError(f"request to {self.url} failed")


def test_the_error_text_and_log_line_of_a_failed_call_hold_no_url(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = QdrantClient(
        _HTTP_URL,
        client=_FailingGetCollections(_HTTP_URL),
        allow_private_network=True,
        timeout=5.0,
    )

    with caplog.at_level(logging.DEBUG, logger="devops_cli.ai.rag.qdrant"):
        with pytest.raises(QdrantClientError) as raised:
            client.list_collections()

    (line,) = (
        record.getMessage()
        for record in caplog.records
        if record.getMessage().startswith("Failed to list Qdrant collections")
    )
    assert [text for text in (str(raised.value), line) if _leaks(text)] == []
    assert "example.com:6333" in str(raised.value)


@pytest.mark.parametrize("url", [_HTTP_URL, _K8S_URL], ids=["http", "k8s"])
def test_the_investigator_warning_names_the_server_by_host_and_port(
    qdrant: Any, caplog: pytest.LogCaptureFixture, url: str
) -> None:
    qdrant.refusing = True
    st = Settings()
    st.ai.rag.enabled = True
    st.qdrant.url = url

    with caplog.at_level(logging.DEBUG, logger="devops_cli.ai.rag.investigator"):
        assert investigate_rag_context("where is the retry policy", settings=st) is None

    (line,) = (
        record.getMessage()
        for record in caplog.records
        if record.getMessage().startswith("Qdrant vector store unreachable")
    )
    host = "example.com:6333" if url == _HTTP_URL else "qdrant.devops:6333"
    assert line == f"Qdrant vector store unreachable at {host}, skipping RAG investigation"


@pytest.mark.parametrize(
    ("url", "message"),
    [
        (
            "user:secret@example.com:6333/prefix/path",
            "Invalid URL: missing scheme or host in qdrant.url",
        ),
        (
            "ftp://user:secret@example.com:6333/prefix/path",
            "Invalid URL for server example.com:6333: "
            "Invalid Qdrant URL scheme 'ftp': must be http or https",
        ),
        (
            "http://user:secret@:6333/prefix/path",
            "Invalid URL: Qdrant URL missing valid hostname",
        ),
        (
            "http://example.com:notaport",
            "Invalid URL: Invalid Qdrant URL: Invalid port: 'notaport'",
        ),
        (
            "http://user:secret@a..b.com/prefix/path",
            "Invalid URL for server a..b.com: Qdrant URL has invalid hostname 'a..b.com'",
        ),
    ],
    ids=["no-scheme", "scheme", "no-host", "parse-error", "host-syntax"],
)
def test_the_error_for_an_invalid_url_names_no_userinfo_and_no_path(url: str, message: str) -> None:
    with pytest.raises(InvalidURLError) as raised:
        QdrantClient(url, allow_private_network=True, timeout=5.0)

    error = raised.value
    assert str(error) == message
    assert _leaks(str(error)) == []
    assert _leaks(repr(error.details)) == []


def test_the_error_for_a_label_with_no_origin_does_not_read_as_a_url() -> None:
    assert str(
        InvalidURLError("file:///etc/passwd", "Only http and https URLs may be requested")
    ) == ("Invalid URL: Only http and https URLs may be requested")
    assert str(InvalidURLError("ftp://example.com", "Unsupported scheme")) == (
        "Invalid URL for server example.com: Unsupported scheme"
    )


class _FailingNative:
    """A native client whose calls fail with an exception that holds the configured URL."""

    def __init__(
        self, *, create_collection: bool = False, create_payload_index: bool = False
    ) -> None:
        self._create_collection = create_collection
        self._create_payload_index = create_payload_index

    def _fail(self) -> None:
        raise RuntimeError(f"request to {_HTTP_URL} failed")

    def get_collections(self) -> None:
        self._fail()

    def get_collection(self, **_: Any) -> None:
        self._fail()

    def create_collection(self, **_: Any) -> bool:
        if not self._create_collection:
            self._fail()
        return True

    def create_payload_index(self, **_: Any) -> None:
        if not self._create_payload_index:
            self._fail()

    def delete_collection(self, **_: Any) -> None:
        self._fail()

    def upsert(self, **_: Any) -> None:
        self._fail()

    def query_points(self, **_: Any) -> None:
        self._fail()

    def count(self, **_: Any) -> None:
        self._fail()

    def scroll(self, **_: Any) -> None:
        self._fail()

    def delete(self, **_: Any) -> None:
        self._fail()

    def set_payload(self, **_: Any) -> None:
        self._fail()


_CALLS: list[tuple[str, dict[str, bool], tuple[Any, ...], dict[str, Any]]] = [
    ("list_collections", {}, (), {}),
    ("get_collection_info", {}, ("col",), {}),
    ("delete_collection", {}, ("col",), {}),
    ("search_points", {}, ("col", [0.1, 0.2]), {"limit": 1}),
    ("count_points", {}, ("col",), {}),
    ("scroll_points", {}, ("col",), {}),
    ("delete_points_by_files", {}, ("col", ["a.py"]), {}),
    ("delete_points_by_project", {}, ("col", "proj"), {}),
    ("set_payload", {}, ("col", {"a": 1}), {"filter_payload": {"k": "v"}}),
]


def _assert_no_url(
    raised: pytest.ExceptionInfo[QdrantClientError], caplog: pytest.LogCaptureFixture
) -> None:
    texts = [str(raised.value), *(record.getMessage() for record in caplog.records)]
    assert [text for text in texts if _leaks(text)] == []
    assert "example.com:6333" in str(raised.value)


@pytest.mark.parametrize(
    ("operation", "flags", "args", "kwargs"),
    _CALLS,
    ids=[
        "list",
        "info",
        "delete",
        "search",
        "count",
        "scroll",
        "delete-files",
        "delete-project",
        "set-payload",
    ],
)
def test_each_failed_call_names_the_server_and_holds_no_url(
    operation: str,
    flags: dict[str, bool],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = QdrantClient(
        _HTTP_URL, client=_FailingNative(**flags), allow_private_network=True, timeout=5.0
    )

    with caplog.at_level(logging.DEBUG, logger="devops_cli.ai.rag.qdrant"):
        with pytest.raises(QdrantClientError) as raised:
            getattr(client, operation)(*args, **kwargs)

    _assert_no_url(raised, caplog)


def test_a_collection_that_cannot_be_created_holds_no_url(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    client = QdrantClient(
        _HTTP_URL, client=_FailingNative(), allow_private_network=True, timeout=5.0
    )
    monkeypatch.setattr(client, "get_collection_info", lambda name: {})

    with caplog.at_level(logging.DEBUG, logger="devops_cli.ai.rag.qdrant"):
        with pytest.raises(QdrantClientError) as raised:
            client.ensure_collection("col", 4)

    _assert_no_url(raised, caplog)


def test_a_payload_index_that_cannot_be_created_holds_no_url(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = QdrantClient(
        _HTTP_URL,
        client=_FailingNative(create_collection=True),
        allow_private_network=True,
        timeout=5.0,
    )

    with caplog.at_level(logging.DEBUG, logger="devops_cli.ai.rag.qdrant"):
        with pytest.raises(QdrantClientError) as raised:
            client._ensure_payload_indexes("col", {})

    _assert_no_url(raised, caplog)


def test_an_upsert_that_fails_holds_no_url(caplog: pytest.LogCaptureFixture) -> None:
    client = QdrantClient(
        _HTTP_URL,
        client=_FailingNative(create_collection=True, create_payload_index=True),
        allow_private_network=True,
        timeout=5.0,
    )
    client._verified_collections["col"] = 4

    with caplog.at_level(logging.DEBUG, logger="devops_cli.ai.rag.qdrant"):
        with pytest.raises(QdrantClientError) as raised:
            client.upsert_points("col", [{"id": "1", "vector": [0.1] * 4, "payload": {}}])

    _assert_no_url(raised, caplog)
