"""Unit tests for RAG integration across AI subcommands."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.ai import _try_retrieve_rag_context
from devops_cli.main import app as main_app

pytestmark = pytest.mark.usefixtures("mock_keyring")

runner = CliRunner()


def test_try_retrieve_rag_context_disabled() -> None:
    with patch("devops_cli.config.settings.load_settings") as mock_st:
        mock_st.return_value.ai.rag.enabled = False
        assert _try_retrieve_rag_context("query") is None


def test_try_retrieve_rag_context_success(
    monkeypatch: pytest.MonkeyPatch, refusing_port: int
) -> None:
    """The knowledge base check finds Qdrant down, refused through `refusing_port`; its retry
    waits return at once, and the retrieved context is returned."""
    monkeypatch.setattr("time.sleep", lambda seconds: None)
    with (
        patch("devops_cli.config.settings.load_settings") as mock_st,
        patch("devops_cli.ai.rag.qdrant.QdrantClient.is_alive", return_value=True),
        patch("devops_cli.ai.rag.retriever.SemanticRetriever.retrieve_context") as mock_ctx,
    ):
        mock_st.return_value.ai.rag.enabled = True
        mock_st.return_value.qdrant.url = f"http://127.0.0.1:{refusing_port}"
        mock_st.return_value.qdrant.collection_prefix = "devops"
        mock_ctx.return_value.has_results = True
        mock_ctx.return_value.formatted_text = "<rag_context>mock content</rag_context>"

        res = _try_retrieve_rag_context("deploy")
        assert res == "<rag_context>mock content</rag_context>"


def test_pipeline_dry_run_with_rag() -> None:
    res = runner.invoke(
        main_app,
        ["--dry-run", "ai", "pipeline", "Review Kubernetes manifests"],
    )
    assert (res.exit_code, "devops ai pipeline" in res.stdout) == (0, True)
