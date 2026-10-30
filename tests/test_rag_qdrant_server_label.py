"""Qdrant log lines, errors and the retriever cache key name the server by host and port.

The configured URL can hold userinfo, which the client sends as Basic authentication, and a path.
No text that the client writes holds either. An address that is not a URL shows as `unknown`.
"""

from __future__ import annotations

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
    "url",
    [
        "user:secret@example.com:6333/prefix/path",
        "ftp://user:secret@example.com:6333/prefix/path",
        "http://user:secret@:6333/prefix/path",
        "http://user:secret@a..b.com/prefix/path",
    ],
    ids=["no-scheme", "scheme", "no-host", "host-syntax"],
)
def test_the_error_for_an_invalid_url_names_no_userinfo_and_no_path(url: str) -> None:
    with pytest.raises(InvalidURLError) as raised:
        QdrantClient(url, allow_private_network=True, timeout=5.0)

    error = raised.value
    assert _leaks(str(error)) == []
    assert _leaks(repr(error.details)) == []


@pytest.mark.parametrize("url", [_HTTP_URL, _K8S_URL], ids=["http", "k8s"])
def test_the_search_cache_key_names_the_server_by_host_and_port(
    monkeypatch: pytest.MonkeyPatch, url: str
) -> None:
    retriever.reset_search_verified_models()
    monkeypatch.setattr(retriever, "_inspect_collection_model", lambda qdrant, name: "model-a")
    client = QdrantClient(url, allow_private_network=True, timeout=5.0)

    retriever._verify_single_collection_for_search(client, "devops_code", "model-a")

    host = "example.com:6333" if url == _HTTP_URL else "qdrant.devops:6333"
    assert list(retriever._SEARCH_VERIFIED_MODELS) == [(host, "devops_code")]
    retriever.reset_search_verified_models()
