"""Tests for RAG CLI commands (ingest, drift, index)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from devops_cli.commands.rag import app
from devops_cli.main import app as main_app
from tests.support.fakes.process import ProcessAnswer, ProcessFake

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


def test_rag_ingest_success(
    config: Any, qdrant: Any, embedder: Any, gh_edge: ProcessFake, tmp_path: Path
) -> None:
    """Verify successful ingestion pass displays table and completion message."""
    config(
        qdrant={"url": "http://127.0.0.1:6333"},
        service={"repos": ["org/repo-a", "org/repo-b"]},
        data={"rag_dir": str(tmp_path / "rag")},
    )
    gh_edge.answer(
        "gh api repos/org/repo-a",
        ProcessAnswer(stdout=json.dumps({"visibility": "public"})),
    )
    gh_edge.answer(
        "gh api repos/org/repo-b",
        ProcessAnswer(stdout=json.dumps({"visibility": "private"})),
    )
    gh_edge.answer(
        lambda call: "ls-remote" in call.argv and "org/repo-a" in " ".join(call.argv),
        ProcessAnswer(stdout="ref: refs/heads/main\tHEAD\nabc123456789\tHEAD\n"),
    )
    gh_edge.answer(
        lambda call: "ls-remote" in call.argv and "org/repo-b" in " ".join(call.argv),
        ProcessAnswer(stdout="ref: refs/heads/dev\tHEAD\ndef987654321\tHEAD\n"),
    )
    result = runner.invoke(app, ["ingest"])
    assert result.exit_code == 0
    assert "org/repo-a" in result.stdout
    assert "org/repo-b" in result.stdout
    assert "indexed" in result.stdout
    assert "2 of 2 repositories indexed" in result.stdout


def test_rag_ingest_with_repo_filter(
    config: Any, qdrant: Any, embedder: Any, gh_edge: ProcessFake, tmp_path: Path
) -> None:
    """Verify --repo options pass repository list to run_ingest_pass."""
    config(
        qdrant={"url": "http://127.0.0.1:6333"},
        service={"repos": ["org/repo-a", "org/repo-b"]},
        data={"rag_dir": str(tmp_path / "rag")},
    )
    gh_edge.answer(
        "gh api repos/org/repo-a",
        ProcessAnswer(stdout=json.dumps({"visibility": "public"})),
    )
    gh_edge.answer(
        lambda call: "ls-remote" in call.argv and "org/repo-a" in " ".join(call.argv),
        ProcessAnswer(stdout="ref: refs/heads/main\tHEAD\nabc123456789\tHEAD\n"),
    )
    result = runner.invoke(app, ["ingest", "--repo", "org/repo-a", "-c", "custom-code"])
    assert result.exit_code == 0
    assert "org/repo-a" in result.stdout
    assert "org/repo-b" not in result.stdout
    assert "1 of 1 repositories indexed" in result.stdout


def test_rag_ingest_json_output(
    config: Any, qdrant: Any, embedder: Any, gh_edge: ProcessFake, tmp_path: Path
) -> None:
    """Verify --json emits serialized list of ingestion results."""
    config(
        qdrant={"url": "http://127.0.0.1:6333"},
        service={"repos": ["org/repo-a"]},
        data={"rag_dir": str(tmp_path / "rag")},
    )
    gh_edge.answer(
        "gh api repos/org/repo-a",
        ProcessAnswer(stdout=json.dumps({"visibility": "public"})),
    )
    gh_edge.answer(
        lambda call: "ls-remote" in call.argv and "org/repo-a" in " ".join(call.argv),
        ProcessAnswer(stdout="ref: refs/heads/main\tHEAD\nabc123456789\tHEAD\n"),
    )
    result = runner.invoke(app, ["ingest", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["repo"] == "org/repo-a"
    assert data[0]["visibility"] == "public"


def test_rag_ingest_failure_exits_nonzero(
    config: Any, qdrant: Any, embedder: Any, gh_edge: ProcessFake, tmp_path: Path
) -> None:
    """Verify failed ingestion causes command to exit with non-zero code."""
    config(
        qdrant={"url": "http://127.0.0.1:6333"},
        service={"repos": ["org/repo-b"]},
        data={"rag_dir": str(tmp_path / "rag")},
    )
    gh_edge.answer(
        lambda call: "ls-remote" in call.argv,
        ProcessAnswer(returncode=1, stderr="fatal: remote error"),
    )
    result = runner.invoke(app, ["ingest"])
    assert result.exit_code != 0
    assert "RAG ingestion failed for repositories: org/repo-b" in result.output


def test_rag_ingest_missing_qdrant_url_raises_configuration_error(config: Any) -> None:
    """Verify unset Qdrant URL raises ConfigurationError naming qdrant.url."""
    config(
        qdrant={"url": None},
        service={"repos": ["org/repo-a"]},
    )
    result = runner.invoke(app, ["ingest"])
    assert result.exit_code != 0
    assert "qdrant.url" in result.output


def test_main_app_ai_rag_ingest() -> None:
    """Verify invocation through devops root application."""
    result = runner.invoke(main_app, ["ai", "rag", "ingest", "--help"])
    assert result.exit_code == 0
    assert "Index managed git repositories" in result.stdout
