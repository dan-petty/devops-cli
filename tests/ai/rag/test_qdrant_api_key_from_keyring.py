"""The Qdrant API key comes from the OS keyring when the caller gives none.

The keyring is faked at its edge. A loopback Qdrant server shows the key the native client sends.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest

from devops_cli.ai.rag.indexer import WorkspaceIndexer, resolve_qdrant_client
from devops_cli.ai.rag.qdrant import QdrantClient
from tests.support.fakes.keyring import FakeKeyring
from tests.support.fakes.qdrant import serving_qdrant

KEY = "vault-qdrant-token"


@pytest.fixture
def stored_key(keyring_store: FakeKeyring) -> FakeKeyring:
    keyring_store.values["qdrant_api_key"] = KEY
    return keyring_store


@pytest.mark.usefixtures("stored_key")
def test_a_client_with_no_key_reads_it_from_the_keyring() -> None:
    assert QdrantClient("http://localhost:6333", allow_private_network=True).api_key == KEY


@pytest.mark.usefixtures("stored_key")
def test_an_explicit_key_wins_over_the_keyring() -> None:
    client = QdrantClient(
        "http://localhost:6333", api_key="explicit-key", allow_private_network=True
    )

    assert client.api_key == "explicit-key"


@pytest.mark.usefixtures("stored_key")
@pytest.mark.filterwarnings("ignore:Api key is used with an insecure connection")
def test_the_native_client_sends_the_keyring_key_to_the_server() -> None:
    with serving_qdrant() as served:
        client = resolve_qdrant_client(served.url, allow_private_network=True)

        assert client.is_alive(force_check=True) is True

    assert served.headers_of_requests()[0]["api-key"] == KEY


@pytest.mark.usefixtures("stored_key")
def test_an_indexer_without_a_client_resolves_an_authenticated_one(
    tmp_path: Path, embedder: Any
) -> None:
    indexer = WorkspaceIndexer(qdrant=None, embedder=embedder, cache_dir=tmp_path)

    assert indexer.qdrant.api_key == KEY


@pytest.mark.usefixtures("stored_key")
def test_an_indexer_gives_a_client_without_a_key_the_keyring_key(
    tmp_path: Path, embedder: Any
) -> None:
    unauthenticated = QdrantClient("http://localhost:6333", api_key="", allow_private_network=True)

    indexer = WorkspaceIndexer(qdrant=unauthenticated, embedder=embedder, cache_dir=tmp_path)

    assert indexer.qdrant.api_key == KEY


def test_a_locked_keyring_leaves_the_client_without_a_key(keyring_store: FakeKeyring) -> None:
    keyring_store.locked = True

    client = QdrantClient("http://localhost:6333", allow_private_network=True)

    assert client.api_key is None


def test_a_client_logs_at_debug_when_the_settings_cannot_be_read(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("DEVOPS_CLI_QDRANT_TIMEOUT", "soon")

    with caplog.at_level(logging.DEBUG, logger="devops_cli.ai.rag.qdrant"):
        client = QdrantClient("http://localhost:6333", allow_private_network=True, timeout=5.0)

    assert client.api_key is None
    assert any(
        "Failed to resolve Qdrant API key from settings" in record.getMessage()
        for record in caplog.records
    )


def test_an_indexer_logs_at_debug_when_the_settings_cannot_be_read(
    tmp_path: Path,
    embedder: Any,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    unauthenticated = QdrantClient(
        "http://localhost:6333", api_key="", allow_private_network=True, timeout=5.0
    )
    monkeypatch.setenv("DEVOPS_CLI_QDRANT_TIMEOUT", "soon")

    with caplog.at_level(logging.DEBUG, logger="devops_cli.ai.rag.indexer"):
        indexer = WorkspaceIndexer(
            qdrant=unauthenticated,
            embedder=embedder,
            cache_dir=tmp_path,
            chunk_size=500,
            chunk_overlap=50,
        )

    assert indexer.qdrant.api_key == ""
    assert any(
        "Failed to resolve Qdrant API key from keyring" in record.getMessage()
        for record in caplog.records
    )
