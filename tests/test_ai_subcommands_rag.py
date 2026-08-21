"""Unit tests for RAG integration across AI subcommands."""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from devops_cli.commands.ai import _try_retrieve_rag_context
from devops_cli.main import app as main_app

runner = CliRunner()


def test_try_retrieve_rag_context_disabled() -> None:
    with patch("devops_cli.config.settings.load_settings") as mock_st:
        mock_st.return_value.ai.rag.enabled = False
        assert _try_retrieve_rag_context("query") is None


def test_try_retrieve_rag_context_success() -> None:
    with (
        patch("devops_cli.config.settings.load_settings") as mock_st,
        patch("devops_cli.ai.rag.qdrant.QdrantClient.is_alive", return_value=True),
        patch("devops_cli.ai.rag.retriever.SemanticRetriever.retrieve_context") as mock_ctx,
    ):
        mock_st.return_value.ai.rag.enabled = True
        mock_st.return_value.qdrant.url = "http://mock:6333"
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
    assert res.exit_code == 0
    assert "delegated command" in res.stdout or "dry-run" in res.stdout
