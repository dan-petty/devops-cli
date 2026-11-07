"""Tests for RAG CLI commands (ingest, drift, index)."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from devops_cli.ai.rag.ingest import IngestResult
from devops_cli.commands.rag import app
from devops_cli.exceptions.ai import RagIngestError
from devops_cli.exceptions.config import ConfigurationError
from devops_cli.main import app as main_app

pytestmark = pytest.mark.usefixtures("keyring_store")

runner = CliRunner(env={"COLUMNS": "250"})


def test_rag_ingest_help() -> None:
    """Verify help message displays for rag ingest command."""
    result = runner.invoke(app, ["ingest", "--help"])
    assert result.exit_code == 0
    assert "Index managed git repositories" in result.stdout
    assert "--repo" in result.stdout


def test_rag_ingest_explain() -> None:
    """Verify explain option executes cleanly."""
    result = runner.invoke(app, ["ingest", "--explain"])
    assert result.exit_code == 0


def test_rag_ingest_dry_run() -> None:
    """Verify dry-run mode returns request plan without execution."""
    result = runner.invoke(app, ["ingest", "--dry-run"])
    assert result.exit_code == 0
    assert "Plan for AI RAG ingest" in result.stdout


def test_rag_ingest_dry_run_json() -> None:
    """Verify dry-run mode returns valid JSON with serialized requests."""
    result = runner.invoke(app, ["ingest", "--dry-run", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data.get("dry_run") is True
    assert "requests" in data


def test_rag_ingest_success() -> None:
    """Verify successful ingestion pass displays table and completion message."""
    mock_results = [
        IngestResult(
            repo="org/repo-a",
            head="abc123456789",
            branch="main",
            visibility="public",
            success=True,
        ),
        IngestResult(
            repo="org/repo-b",
            head="def987654321",
            branch="dev",
            visibility="private",
            success=True,
        ),
    ]
    with patch("devops_cli.ai.rag.ingest.run_ingest_pass", return_value=mock_results) as mock_run:
        result = runner.invoke(app, ["ingest"])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(repo_filter=None, code_collection=None)
        assert "org/repo-a" in result.stdout
        assert "org/repo-b" in result.stdout
        assert "indexed" in result.stdout
        assert "2 of 2 repositories indexed" in result.stdout


def test_rag_ingest_with_repo_filter() -> None:
    """Verify --repo options pass repository list to run_ingest_pass."""
    mock_results = [
        IngestResult(
            repo="org/repo-a",
            head="abc123456789",
            branch="main",
            visibility="public",
            success=True,
        ),
    ]
    with patch("devops_cli.ai.rag.ingest.run_ingest_pass", return_value=mock_results) as mock_run:
        result = runner.invoke(app, ["ingest", "--repo", "org/repo-a", "-c", "custom-code"])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(repo_filter=["org/repo-a"], code_collection="custom-code")


def test_rag_ingest_json_output() -> None:
    """Verify --json emits serialized list of ingestion results."""
    mock_results = [
        IngestResult(
            repo="org/repo-a",
            head="abc12345",
            branch="main",
            visibility="public",
            success=True,
        ),
    ]
    with patch("devops_cli.ai.rag.ingest.run_ingest_pass", return_value=mock_results):
        result = runner.invoke(app, ["ingest", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["repo"] == "org/repo-a"
        assert data[0]["visibility"] == "public"


def test_rag_ingest_failure_exits_nonzero() -> None:
    """Verify RagIngestError causes command to exit with non-zero code."""
    with patch(
        "devops_cli.ai.rag.ingest.run_ingest_pass",
        side_effect=RagIngestError("RAG ingestion failed for repositories: org/repo-b"),
    ):
        result = runner.invoke(app, ["ingest"])
        assert result.exit_code != 0
        assert "RAG ingestion failed for repositories: org/repo-b" in result.output


def test_rag_ingest_missing_qdrant_url_raises_configuration_error() -> None:
    """Verify unset Qdrant URL raises ConfigurationError naming qdrant.url."""
    with patch(
        "devops_cli.ai.rag.ingest.run_ingest_pass",
        side_effect=ConfigurationError(
            "No Qdrant vector store URL configured. Run: devops config set qdrant.url <url>",
            key="qdrant.url",
        ),
    ):
        result = runner.invoke(app, ["ingest"])
        assert result.exit_code != 0
        assert "qdrant.url" in result.output


def test_main_app_ai_rag_ingest() -> None:
    """Verify invocation through devops root application."""
    result = runner.invoke(main_app, ["ai", "rag", "ingest", "--help"])
    assert result.exit_code == 0
    assert "Index managed git repositories" in result.stdout
