"""RAG's QdrantClient and WorkspaceIndexer resolve the Qdrant API key from the OS keyring.

Kept apart from tests/test_k8s_qdrant_security.py, whose deploy-stack and manifest checks have a
1 s budget that importing the RAG client alone exceeds.
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def test_qdrant_client_resolves_keyring_secret() -> None:
    """Verify QdrantClient automatically resolves API key from OS Keyring when omitted."""
    from devops_cli.ai.rag.qdrant import QdrantClient

    with patch(
        "devops_cli.config.settings.get_qdrant_api_key", return_value="resolved-keyring-key"
    ):
        client = QdrantClient("http://localhost:6333", allow_private_network=True)
        assert client.api_key == "resolved-keyring-key"

    # Explicit api_key overrides keyring lookup
    client_explicit = QdrantClient(
        "http://localhost:6333", api_key="explicit-key", allow_private_network=True
    )
    assert client_explicit.api_key == "explicit-key"


def test_workspace_indexer_resolves_keyring_authenticated_client(tmp_path: Path) -> None:
    """Verify WorkspaceIndexer and resolve_qdrant_client authenticate via OS Keyring."""
    from devops_cli.ai.rag.indexer import WorkspaceIndexer, resolve_qdrant_client
    from devops_cli.ai.rag.qdrant import QdrantClient

    with patch("devops_cli.config.settings.get_qdrant_api_key", return_value="vault-qdrant-token"):
        client = resolve_qdrant_client("http://localhost:6333", allow_private_network=True)
        assert client.api_key == "vault-qdrant-token"

        mock_embedder = MagicMock()
        mock_embedder.model = "test-model"

        # 1. When qdrant client is omitted, it must resolve automatically via Keyring
        indexer = WorkspaceIndexer(qdrant=None, embedder=mock_embedder, cache_dir=tmp_path)
        assert indexer.qdrant is not None
        assert indexer.qdrant.api_key == "vault-qdrant-token"

        # 2. When an unauthenticated qdrant client is provided, it must backfill from Keyring
        unauth_client = QdrantClient(
            "http://localhost:6333", api_key=None, allow_private_network=True
        )
        unauth_client.api_key = None  # force null
        indexer_backfill = WorkspaceIndexer(
            qdrant=unauth_client, embedder=mock_embedder, cache_dir=tmp_path
        )
        assert indexer_backfill.qdrant.api_key == "vault-qdrant-token"


def test_workspace_indexer_debug_logs_on_keyring_failure(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify WorkspaceIndexer logs at DEBUG level when keyring lookup fails."""
    from devops_cli.ai.rag.indexer import WorkspaceIndexer
    from devops_cli.ai.rag.qdrant import QdrantClient

    caplog.set_level(logging.DEBUG)
    mock_embedder = MagicMock()
    mock_embedder.model = "test-model"
    unauth_client = QdrantClient("http://localhost:6333", api_key=None, allow_private_network=True)
    unauth_client.api_key = None

    with patch(
        "devops_cli.config.settings.get_qdrant_api_key",
        side_effect=RuntimeError("Keyring unavailable"),
    ):
        indexer = WorkspaceIndexer(qdrant=unauth_client, embedder=mock_embedder, cache_dir=tmp_path)
        assert indexer.qdrant.api_key is None
        assert any(
            "Failed to resolve Qdrant API key from keyring" in rec.message for rec in caplog.records
        )


def test_qdrant_client_debug_logs_on_settings_failure(caplog: pytest.LogCaptureFixture) -> None:
    """Verify QdrantClient logs at DEBUG level when settings resolution fails."""
    from devops_cli.ai.rag.qdrant import QdrantClient

    caplog.set_level(logging.DEBUG)
    with patch(
        "devops_cli.config.settings.get_qdrant_api_key",
        side_effect=RuntimeError("Keyring unavailable"),
    ):
        client = QdrantClient("http://localhost:6333", allow_private_network=True)
        assert client.api_key is None
        assert any(
            "Failed to resolve Qdrant API key from settings" in rec.message
            for rec in caplog.records
        )
