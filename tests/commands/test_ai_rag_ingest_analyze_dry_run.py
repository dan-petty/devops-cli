"""Tests for dry-run request plans and classifications across 21 AI rag, ingest, analyze, and research commands.

Issue #2244: The dry-run rule (#412) states that a dry run makes no external request and
returns the requests that the real run would make.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from devops_cli.commands.ai_ingest import (
    index_libraries,
    ingest_docs,
    ingest_library,
    query_library,
)
from devops_cli.commands.ai_research import (
    analogies_cmd,
    annotate_cmd,
    forage_cmd,
    model_cmd,
    socratic_cmd,
)
from devops_cli.commands.analyze import (
    analyze_branch,
    analyze_main,
    analyze_path,
    analyze_pr,
)
from devops_cli.commands.rag import (
    clear_cmd as rag_clear_cmd,
)
from devops_cli.commands.rag import (
    drift_cmd as rag_drift_cmd,
)
from devops_cli.commands.rag import (
    index_cmd as rag_index_cmd,
)
from devops_cli.commands.rag import (
    index_kb_cmd as rag_index_kb_cmd,
)
from devops_cli.commands.rag import (
    ingest_cmd as rag_ingest_cmd,
)
from devops_cli.commands.rag import (
    rag_main,
)
from devops_cli.commands.rag import (
    search as rag_search_cmd,
)
from devops_cli.commands.rag import (
    status_cmd as rag_status_cmd,
)
from devops_cli.main import app
from tests.support.dry_run_classes import misclassified

pytestmark = pytest.mark.usefixtures("refuse_requests")

runner = CliRunner()

REQUEST_PLAN_COMMANDS = [
    ("ai analyze branch", analyze_branch, ["ai", "analyze", "branch", "--dry-run"]),
    ("ai analyze path", analyze_path, ["ai", "analyze", "path", ".", "--dry-run"]),
    ("ai analyze pr", analyze_pr, ["ai", "analyze", "pr", "123", "--dry-run"]),
    (
        "ai ingest docs",
        ingest_docs,
        ["ai", "ingest", "docs", "https://example.com/docs", "--dry-run"],
    ),
    (
        "ai ingest index-libraries",
        index_libraries,
        ["ai", "ingest", "index-libraries", "--dry-run"],
    ),
    (
        "ai ingest query-library",
        query_library,
        ["ai", "ingest", "query-library", "FastAPI", "--dry-run"],
    ),
    ("ai rag clear", rag_clear_cmd, ["ai", "rag", "clear", "--force", "--dry-run"]),
    ("ai rag drift", rag_drift_cmd, ["ai", "rag", "drift", "--dry-run"]),
    ("ai rag index", rag_index_cmd, ["ai", "rag", "index", "--dry-run"]),
    ("ai rag index-kb", rag_index_kb_cmd, ["ai", "rag", "index-kb", "--dry-run"]),
    ("ai rag ingest", rag_ingest_cmd, ["ai", "rag", "ingest", "--dry-run"]),
    ("ai rag query", rag_search_cmd, ["ai", "rag", "query", "search test", "--dry-run"]),
    ("ai rag search", rag_search_cmd, ["ai", "rag", "search", "search test", "--dry-run"]),
    ("ai rag status", rag_status_cmd, ["ai", "rag", "status", "--dry-run"]),
    (
        "ai research analogies",
        analogies_cmd,
        ["ai", "research", "analogies", "--query", "concept", "--dry-run"],
    ),
    ("ai research model", model_cmd, ["ai", "research", "model", "qwen", "--dry-run"]),
    ("ai research socratic", socratic_cmd, ["ai", "research", "socratic", "question", "--dry-run"]),
]

IN_PLACE_COMMANDS = [
    ("ai analyze", analyze_main, ["--dry-run", "ai", "analyze", "--explain"]),
    ("ai ingest library", ingest_library, ["--dry-run", "ai", "ingest", "library", "devops_cli"]),
    ("ai rag", rag_main, ["--dry-run", "ai", "rag", "--explain"]),
    (
        "ai research annotate",
        annotate_cmd,
        ["--dry-run", "ai", "research", "annotate", "README.md"],
    ),
]
"""The no-external-request commands that run on this checkout."""

FORAGE_COMMAND = (
    "ai research forage",
    forage_cmd,
    ["--dry-run", "ai", "research", "forage", "pyproject.toml"],
)
"""Forage crawls the repository and reads the git history of each file it visits, so its test
gives it a directory of one file with `--repo`."""

NO_EXTERNAL_REQUEST_COMMANDS = [*IN_PLACE_COMMANDS, FORAGE_COMMAND]


def test_commands_carry_their_dry_run_class() -> None:
    """Commands that call a model, an index or GitHub carry request-plan; local ones no-external-request."""
    assert misclassified(REQUEST_PLAN_COMMANDS, "request-plan") == {}
    assert misclassified(NO_EXTERNAL_REQUEST_COMMANDS, "no-external-request") == {}


@pytest.mark.parametrize("name,callback,argv", REQUEST_PLAN_COMMANDS)
def test_request_plan_commands_run_cleanly(name: str, callback: Any, argv: list[str]) -> None:
    """Execute each request-plan command with --dry-run and verify clean exit and plan output."""
    result = runner.invoke(app, argv)
    assert result.exit_code == 0, f"{name} failed with {result.output}"
    assert "Plan for" in result.output, (
        f"Expected 'Plan for' header in {name} output, got: {result.output}"
    )


@pytest.mark.parametrize("name,callback,argv", IN_PLACE_COMMANDS)
def test_no_external_request_commands_run(name: str, callback: Any, argv: list[str]) -> None:
    """Test commands classified as no-external-request run normally without error."""
    result = runner.invoke(app, argv)
    assert result.exit_code == 0, f"{name} failed with {result.output}"


def test_forage_dry_run_runs_on_the_repository_it_is_given(tmp_path: Path) -> None:
    """The forage dry run runs normally on a directory of one file that `--repo` names."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "example"\n', encoding="utf-8")
    name, _, argv = FORAGE_COMMAND

    result = runner.invoke(app, [*argv, "--repo", str(tmp_path)])

    assert result.exit_code == 0, f"{name} failed with {result.output}"


def test_ai_ingest_and_rag_dry_run_json_formats(tmp_path: Path) -> None:
    """Verify json output formats for ingest and rag drift dry runs."""
    doc_file = tmp_path / "guide.md"
    doc_file.write_text("# Doc\nSome text.", encoding="utf-8")

    res_docs = runner.invoke(
        app,
        ["ai", "ingest", "docs", str(doc_file), "--dry-run", "--format", "json"],
    )
    assert res_docs.exit_code == 0
    assert '"is_dry_run": true' in res_docs.output

    res_idx = runner.invoke(
        app,
        [
            "ai",
            "ingest",
            "index-libraries",
            "--dir",
            str(tmp_path),
            "--dry-run",
            "--format",
            "json",
        ],
    )
    assert res_idx.exit_code == 0
    assert '"dry_run": true' in res_idx.output

    res_query = runner.invoke(
        app,
        ["ai", "ingest", "query-library", "search", "--dry-run", "--format", "json"],
    )
    assert res_query.exit_code == 0
    assert '"dry_run": true' in res_query.output

    res_drift = runner.invoke(
        app,
        ["ai", "rag", "drift", str(tmp_path), "--dry-run", "--json"],
    )
    assert res_drift.exit_code == 0
    assert '"dry_run": true' in res_drift.output


def test_plan_ai_targets_with_openai_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify embedding and chat targets resolve properly with openai provider."""
    from devops_cli.ai.ai_plans import _get_llm_chat_target, _get_llm_embedding_target

    monkeypatch.setenv("DEVOPS_CLI_AI_PROVIDER", "openai")
    monkeypatch.setenv("DEVOPS_CLI_AI_API_BASE_URL", "https://api.example.com/v1")

    assert _get_llm_chat_target() == "https://api.example.com/v1/chat/completions"
    assert _get_llm_embedding_target() == "https://api.example.com/v1/embeddings"
