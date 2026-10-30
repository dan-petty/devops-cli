"""Qdrant log lines, errors and the retriever cache key name the server by host and port.

The configured URL can hold userinfo, which the client sends as Basic authentication, and a path.
No text that the client writes holds either. An address that is not a URL shows as `unknown`.
"""

from __future__ import annotations

import hashlib
import logging
from unittest.mock import MagicMock

import pytest

from devops_cli.ai.rag import retriever
from devops_cli.ai.rag.investigator import _get_or_create_retriever, clear_investigation_cache
from devops_cli.ai.rag.qdrant import QdrantClient
from devops_cli.config.settings import Settings
from devops_cli.exceptions import InvalidURLError

pytestmark = pytest.mark.usefixtures("keyring_store")

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
        "empty",
    ],
)
def test_the_label_names_the_server_by_host_and_port(url: str, label: str) -> None:
    from devops_cli.ai.rag.qdrant import qdrant_server_label

    assert qdrant_server_label(url) == label


@pytest.mark.parametrize("url", [_HTTP_URL, _K8S_URL], ids=["http", "k8s"])
def test_the_client_log_line_of_list_collections_names_the_server_by_host_and_port(
    caplog: pytest.LogCaptureFixture, url: str
) -> None:
    client = QdrantClient(url, allow_private_network=True, timeout=5.0)
    native = MagicMock()
    native.get_collections.side_effect = ConnectionError("Connection refused")
    client._client = native
    client._build_client = lambda: native

    with caplog.at_level(logging.DEBUG, logger="devops_cli.ai.rag.qdrant"):
        with pytest.raises(Exception, match="Connection refused"):
            client.list_collections()

    (line,) = (
        record.getMessage()
        for record in caplog.records
        if record.getMessage().startswith("Failed to list Qdrant collections")
    )
    host = "example.com:6333" if url == _HTTP_URL else "qdrant.devops:6333"
    assert line == f"Failed to list Qdrant collections from {host}: Connection refused"


@pytest.mark.parametrize("url", [_HTTP_URL, _K8S_URL], ids=["http", "k8s"])
def test_the_investigator_warning_names_the_server_by_host_and_port(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, url: str
) -> None:
    clear_investigation_cache()
    monkeypatch.setattr(QdrantClient, "is_alive", lambda self, **_: False)
    st = Settings()
    st.ai.allow_private_network = True
    st.qdrant.url = url

    with caplog.at_level(logging.DEBUG, logger="devops_cli.ai.rag.investigator"):
        assert _get_or_create_retriever(st, None, None) is None

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
            "http://user:secret@a..b.com/prefix/path",
            "Invalid URL for server a..b.com: Qdrant URL has invalid hostname 'a..b.com'",
        ),
    ],
    ids=["no-scheme", "scheme", "no-host", "host-syntax"],
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


def test_the_broker_veto_of_a_scheme_says_which_problem_it_is() -> None:
    from devops_cli.http.broker import HttpClientBroker
    from devops_cli.http.egress import EgressLevel

    with HttpClientBroker() as broker:
        client = broker.get_client(EgressLevel.PUBLIC)
        request = client.build_request("GET", "file:///etc/passwd")
        with pytest.raises(InvalidURLError) as raised:
            client.send(request)

    assert str(raised.value) == "Invalid URL: Only http and https URLs may be requested"


@pytest.mark.parametrize("url", [_HTTP_URL, _K8S_URL], ids=["http", "k8s"])
def test_the_search_cache_key_names_the_server_by_label_and_digest(
    monkeypatch: pytest.MonkeyPatch, url: str
) -> None:
    retriever.reset_search_verified_models()
    monkeypatch.setattr(retriever, "_inspect_collection_model", lambda qdrant, name: "model-a")
    client = QdrantClient(url, allow_private_network=True, timeout=5.0)

    retriever._verify_single_collection_for_search(client, "devops_code", "model-a")

    ((label, digest, collection),) = retriever._SEARCH_VERIFIED_MODELS
    assert (label, collection) == (client.server_label, "devops_code")
    assert digest == hashlib.sha256(client.base_url.encode()).hexdigest()
    assert _leaks(repr(retriever._SEARCH_VERIFIED_MODELS)) == []
    retriever.reset_search_verified_models()


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("http://example.com", "https://example.com"),
        ("http://example.com/qdrant-a", "http://example.com/qdrant-b"),
    ],
    ids=["scheme", "path-prefix"],
)
def test_two_servers_with_one_label_keep_two_cache_keys(
    monkeypatch: pytest.MonkeyPatch, first: str, second: str
) -> None:
    """The second server is checked against its own model, not skipped or compared with the first."""
    retriever.reset_search_verified_models()
    recorded = {first: "model-a", second: "model-b"}
    monkeypatch.setattr(
        retriever, "_inspect_collection_model", lambda qdrant, name: recorded[qdrant.base_url]
    )
    one = QdrantClient(first, allow_private_network=True, timeout=5.0)
    two = QdrantClient(second, allow_private_network=True, timeout=5.0)

    retriever._verify_single_collection_for_search(one, "devops_code", "model-a")
    with pytest.raises(Exception, match="model"):
        retriever._verify_single_collection_for_search(two, "devops_code", "model-a")

    assert len(retriever._SEARCH_VERIFIED_MODELS) == 2
    retriever.reset_search_verified_models()


def test_two_malformed_addresses_that_both_show_unknown_keep_two_cache_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    retriever.reset_search_verified_models()
    monkeypatch.setattr(retriever, "_inspect_collection_model", lambda qdrant, name: "model-a")
    first = MagicMock(base_url="k8s://devops", server_label="unknown")
    second = MagicMock(base_url="k8s://staging", server_label="unknown")

    retriever._verify_single_collection_for_search(first, "devops_code", "model-a")
    retriever._verify_single_collection_for_search(second, "devops_code", "model-a")

    assert len(retriever._SEARCH_VERIFIED_MODELS) == 2
    retriever.reset_search_verified_models()
