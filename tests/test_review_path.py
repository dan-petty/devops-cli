"""Tests for the review command group."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx2
import pytest
from typer.testing import CliRunner

from devops_cli.ai.client import LLMClient
from devops_cli.ai.review.runner import _collect_file_blocks
from devops_cli.config.defaults import DEFAULT_REVIEW_TIMEOUT_SECONDS
from devops_cli.config.settings import AIConfig
from devops_cli.main import app
from devops_cli.models.ai import ChatMessage
from devops_cli.review.diff import diff_blocks
from devops_cli.review.session import ReviewSessionStore
from tests.llm_stream_fakes import route_client

runner = CliRunner(env={"COLUMNS": "250", "NO_COLOR": "1", "TERM": "dumb"})


def test_diff_blocks_keeps_files_on_separate_blocks() -> None:
    diff = "diff --git a/one.py b/one.py\n+line one\ndiff --git a/two.py b/two.py\n+line two\n"

    blocks = diff_blocks(diff)

    assert len(blocks) == 2
    assert "one.py" in blocks[0]
    assert "two.py" in blocks[1]


def test_collect_file_blocks_yields_one_block_per_file(tmp_path: Path) -> None:
    text = "".join(f"print({i})\n" for i in range(120))
    file_path = tmp_path / "big.py"
    file_path.write_text(text, encoding="utf-8")
    blocks = _collect_file_blocks(tmp_path, "*.py")

    assert len(blocks) == 1
    assert "### File: big.py\n" in blocks[0]
    assert "```py" in blocks[0]
    assert "1\tprint(0)" in blocks[0]
    assert "120\tprint(119)" in blocks[0]


def test_review_client_uses_long_read_timeout_for_chat_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A review chat runs far longer than a generic HTTP call and must not be cut short.

    The timeout moved from the client to the request when providers began sharing a pooled
    connection: a shared client cannot carry one caller's timeout. This asserts it at the
    request, which is where it now takes effect -- the first version of that change dropped
    it here entirely, and every long review would have aborted.
    """
    client = LLMClient(
        AIConfig(provider="ollama", ollama_urls=["http://localhost:11434"]),
        request_timeout_seconds=DEFAULT_REVIEW_TIMEOUT_SECONDS,
    )
    sent = route_client(
        client,
        monkeypatch,
        lambda request: httpx2.Response(200, json={"message": {"content": "ok"}}),
    )

    client._ollama_messages("system", [ChatMessage(role="user", content="user")])

    assert [request.extensions["timeout"]["read"] for request in sent] == [
        DEFAULT_REVIEW_TIMEOUT_SECONDS
    ]


def test_review_path_append_cache_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that --append-cache flag is parsed and passed to review clients."""
    from typer.testing import CliRunner

    from devops_cli.commands.review import app as review_app

    runner = CliRunner()
    test_f = tmp_path / "test.py"
    test_f.write_text("print('hello')\n", encoding="utf-8")

    captured_kwargs: dict[str, Any] = {}

    def mock_make_clients(settings: Any, **kwargs: Any) -> Any:
        captured_kwargs.update(kwargs)
        from unittest.mock import MagicMock

        return MagicMock()

    monkeypatch.setattr(
        "devops_cli.ai.review.runner._is_allowed_review_boundary", lambda *a, **kw: True
    )
    monkeypatch.setattr("devops_cli.commands.review._make_review_clients", mock_make_clients)
    monkeypatch.setattr("devops_cli.commands.review._execute_review_workflow", lambda *a, **kw: [])

    res = runner.invoke(
        review_app,
        [
            "path",
            str(test_f),
            "--append-cache",
            "--no-pre-analysis",
            "--no-static-scan",
        ],
    )
    assert res.exit_code == 0
    assert captured_kwargs.get("append_cache") is True


def test_run_review_dry_run_skips_client_calls(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, review_store: type[ReviewSessionStore]
) -> None:
    """Verify a dry-run review calls no LLM client, writes no session files, and records no stats session (#872)."""
    from devops_cli.ai.review import runner as review_runner

    reviews_dir = review_store.root()
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    (target_dir / "app.py").write_text("print('hello')\n", encoding="utf-8")

    monkeypatch.setenv("DEVOPS_CLI_DRY_RUN", "true")

    call_count = 0

    class DummyClient:
        def chat(self, *args: object, **kwargs: object) -> str:
            nonlocal call_count
            call_count += 1
            return "should-not-be-called"

    results = review_runner._execute_review_workflow(
        ["### File: app.py\n```py\n   1 | print('hello')\n```\n"],
        "Dry Run Review",
        False,
        review_runner.ReviewClients.model_construct(analysis=DummyClient()),
        target_dir=target_dir,
        session_id="20261016-dryrun",
    )
    monkeypatch.delenv("DEVOPS_CLI_DRY_RUN", raising=False)
    from devops_cli.dry_run.state import set_dry_run

    set_dry_run(False)
    stats_res = runner.invoke(app, ["review", "stats", "--reviews-dir", str(reviews_dir)])

    assert (
        call_count,
        len(results),
        list(reviews_dir.iterdir()),
        stats_res.exit_code,
        "No saved review sessions" in stats_res.output,
    ) == (0, 1, [], 0, True)


def test_dry_run_routed_files_only_leaves_reviews_dir_empty(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, review_store: type[ReviewSessionStore]
) -> None:
    """Verify a dry-run review whose only change is a routed file creates no session directory (#872)."""
    from unittest.mock import MagicMock

    from devops_cli.ai.review import runner as review_runner

    reviews_dir = review_store.root()
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    (target_dir / "uv.lock").write_text("version = 1\n", encoding="utf-8")

    monkeypatch.setenv("DEVOPS_CLI_DRY_RUN", "true")

    results = review_runner._execute_review_workflow(
        [],
        "Routed Dry Run",
        False,
        review_runner.ReviewClients.model_construct(analysis=MagicMock()),
        target_dir=target_dir,
        routed_files=["uv.lock"],
        session_id="20261016-routed-dryrun",
    )

    assert (len(results), list(reviews_dir.iterdir())) == (1, [])
