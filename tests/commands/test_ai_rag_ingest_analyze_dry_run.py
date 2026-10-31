"""Tests for dry-run request plans and classifications across 21 AI rag, ingest, analyze, and research commands.

Issue #2244: The dry-run rule (#412) states that a dry run makes no external request and
returns the requests that the real run would make.
"""

from __future__ import annotations

import json
import socket
import subprocess
from pathlib import Path
from typing import Any

import httpx2
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
    rag_main,
)
from devops_cli.commands.rag import (
    search as rag_search_cmd,
)
from devops_cli.commands.rag import (
    status_cmd as rag_status_cmd,
)
from devops_cli.dry_run import get_dry_run_class
from devops_cli.main import app

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

NO_EXTERNAL_REQUEST_COMMANDS = [
    ("ai analyze", analyze_main, ["--dry-run", "ai", "analyze", "--explain"]),
    ("ai ingest library", ingest_library, ["--dry-run", "ai", "ingest", "library", "devops_cli"]),
    ("ai rag", rag_main, ["--dry-run", "ai", "rag", "--explain"]),
    (
        "ai research annotate",
        annotate_cmd,
        ["--dry-run", "ai", "research", "annotate", "README.md"],
    ),
    ("ai research forage", forage_cmd, ["--dry-run", "ai", "research", "forage", "pyproject.toml"]),
]


@pytest.fixture(autouse=True)
def guard_external_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure no real socket, subprocess, or HTTP call executes during dry-run tests."""
    real_run = subprocess.run
    real_popen = subprocess.Popen
    real_check_output = subprocess.check_output

    def _block_socket(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("Network socket call attempted during dry-run preview")

    def _block_subprocess(cmd: Any, *args: Any, **kwargs: Any) -> Any:
        cmd_seq = cmd if isinstance(cmd, (list, tuple)) else [cmd]
        first = str(cmd_seq[0]) if cmd_seq else ""
        if Path(first).name == "git":
            return real_run(cmd, *args, **kwargs)
        raise AssertionError(f"Subprocess execution attempted during dry-run preview: {cmd}")

    def _block_popen(cmd: Any, *args: Any, **kwargs: Any) -> Any:
        cmd_seq = cmd if isinstance(cmd, (list, tuple)) else [cmd]
        first = str(cmd_seq[0]) if cmd_seq else ""
        if Path(first).name == "git":
            return real_popen(cmd, *args, **kwargs)
        raise AssertionError(f"Subprocess execution attempted during dry-run preview: {cmd}")

    def _block_check_output(cmd: Any, *args: Any, **kwargs: Any) -> Any:
        cmd_seq = cmd if isinstance(cmd, (list, tuple)) else [cmd]
        first = str(cmd_seq[0]) if cmd_seq else ""
        if Path(first).name == "git":
            return real_check_output(cmd, *args, **kwargs)
        raise AssertionError(f"Subprocess execution attempted during dry-run preview: {cmd}")

    def _block_httpx(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("HTTP request attempted during dry-run preview")

    monkeypatch.setattr(socket.socket, "connect", _block_socket)
    monkeypatch.setattr(subprocess, "Popen", _block_popen)
    monkeypatch.setattr(subprocess, "run", _block_subprocess)
    monkeypatch.setattr(subprocess, "check_output", _block_check_output)
    monkeypatch.setattr(httpx2.Client, "send", _block_httpx)
    monkeypatch.setattr(httpx2.HTTPTransport, "handle_request", _block_httpx)


def test_dry_run_classes_decorated() -> None:
    """Verify that each command callback is decorated with its assigned dry-run class."""
    for name, callback, _ in REQUEST_PLAN_COMMANDS:
        assert get_dry_run_class(callback) == "request-plan", (
            f"Expected {name} to have dry-run class 'request-plan'"
        )

    for name, callback, _ in NO_EXTERNAL_REQUEST_COMMANDS:
        assert get_dry_run_class(callback) == "no-external-request", (
            f"Expected {name} to have dry-run class 'no-external-request'"
        )


def test_all_21_commands_removed_from_gaps() -> None:
    """Verify all 21 commands have been excised from tests/fixtures/dry_run_gaps.json."""
    gaps_path = Path("tests/fixtures/dry_run_gaps.json")
    assert gaps_path.exists()
    gaps = json.loads(gaps_path.read_text(encoding="utf-8"))

    expected_removed = [name for name, _, _ in REQUEST_PLAN_COMMANDS] + [
        name for name, _, _ in NO_EXTERNAL_REQUEST_COMMANDS
    ]

    for cmd_path in set(expected_removed):
        assert cmd_path not in gaps, f"Command '{cmd_path}' should be removed from gaps"


@pytest.mark.parametrize("name,callback,argv", REQUEST_PLAN_COMMANDS)
def test_request_plan_commands_run_cleanly(name: str, callback: Any, argv: list[str]) -> None:
    """Execute each request-plan command with --dry-run and verify clean exit and plan output."""
    result = runner.invoke(app, argv)
    assert result.exit_code == 0, f"{name} failed with {result.output}"
    assert "Plan for" in result.output, (
        f"Expected 'Plan for' header in {name} output, got: {result.output}"
    )


@pytest.mark.parametrize("name,callback,argv", REQUEST_PLAN_COMMANDS)
def test_request_plan_flag_order_global_dry_run(name: str, callback: Any, argv: list[str]) -> None:
    """Test global flag order: devops --dry-run <command>."""
    sub_args = [arg for arg in argv if arg != "--dry-run"]
    global_argv = ["--dry-run", *sub_args]
    result = runner.invoke(app, global_argv)
    assert result.exit_code == 0, f"Global --dry-run failed for {name} with: {result.output}"
    assert "Plan for" in result.output, (
        f"Expected 'Plan for' header in global dry-run {name}, got: {result.output}"
    )


@pytest.mark.parametrize("name,callback,argv", NO_EXTERNAL_REQUEST_COMMANDS)
def test_no_external_request_commands_run(name: str, callback: Any, argv: list[str]) -> None:
    """Test commands classified as no-external-request run normally without error."""
    result = runner.invoke(app, argv)
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
