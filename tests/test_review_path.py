"""Tests for the review command group."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import httpx2
import pytest
from typer.testing import CliRunner

from devops_cli.ai.client import LLMClient
from devops_cli.ai.personas import PERSONAS, Persona
from devops_cli.ai.review.chunker import (
    _paginate_file_diff_block,
    _split_diff_into_file_blocks,
    _split_source_file_blocks,
    diff_pages,
)
from devops_cli.ai.review.classification import _persona_system_prompt
from devops_cli.config.defaults import DEFAULT_REVIEW_TIMEOUT_SECONDS
from devops_cli.config.settings import AIConfig
from devops_cli.main import app
from devops_cli.models.ai import ChatMessage
from tests.llm_stream_fakes import route_client

runner = CliRunner(env={"COLUMNS": "250", "NO_COLOR": "1", "TERM": "dumb"})


def test_review_path_help_includes_persona_option() -> None:
    result = runner.invoke(app, ["review", "path", "--help"])

    assert result.exit_code == 0
    clean_output = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", result.output)
    assert "--persona" in clean_output


def test_persona_system_prompt_includes_agents_md_when_present() -> None:
    persona = PERSONAS[Persona.DEVSECOPS]

    prompt = _persona_system_prompt(persona, "Use latest Python by policy.")

    assert persona.system_prompt in prompt
    assert "Use latest Python by policy." in prompt
    assert "Do not raise findings that merely restate or contradict" in prompt


def test_persona_system_prompt_unchanged_when_no_agents_md() -> None:
    persona = PERSONAS[Persona.DEVSECOPS]
    prompt = _persona_system_prompt(persona, "")

    assert prompt.startswith(persona.system_prompt)
    assert "Security & Prompt Isolation Guardrails" in prompt
    assert "Project Instructions" not in prompt


def test_diff_pages_keeps_small_files_on_separate_pages() -> None:
    diff = "diff --git a/one.py b/one.py\n+line one\ndiff --git a/two.py b/two.py\n+line two\n"

    pages = diff_pages(diff, max_chars=1000)

    assert len(pages) == 2
    assert "one.py" in pages[0]
    assert "two.py" in pages[1]


def test_paginate_file_diff_block_splits_across_windows_without_dropping_content() -> None:
    preamble = "diff --git a/one.py b/one.py\n--- a/one.py\n+++ b/one.py\n@@ -1,10 +1,10 @@\n"
    body = "".join(f"+line-{i:02d}\n" for i in range(20))
    block = preamble + body

    windows = _paginate_file_diff_block(block, max_chars=100)

    assert len(windows) > 1
    combined = "".join(windows)
    assert "one.py" in combined
    assert "line-00" in combined
    assert "line-19" in combined


def test_paginate_file_diff_block_hard_splits_an_oversized_single_block() -> None:
    huge_block = "diff --git a/huge.py b/huge.py\n" + "".join(f"+line-{i}\n" for i in range(60))

    pages = _paginate_file_diff_block(huge_block, max_chars=100)

    assert len(pages) > 1
    assert "huge.py" in pages[0]


def test_split_diff_into_file_blocks_separates_per_file() -> None:
    diff = "diff --git a/one.py b/one.py\n+one\ndiff --git a/two.py b/two.py\n+two\n"

    blocks = _split_diff_into_file_blocks(diff)

    assert len(blocks) == 2
    assert blocks[0].startswith("diff --git a/one.py")
    assert blocks[1].startswith("diff --git a/two.py")


def test_diff_pages_covers_every_file_when_paginated() -> None:
    diff = (
        "diff --git a/one.py b/one.py\n" + ("+" + "a" * 80 + "\n") * 3 + "diff --git a/two.py"
        " b/two.py\n" + ("+" + "b" * 80 + "\n") * 3
    )

    pages = diff_pages(diff, max_chars=200)

    assert len(pages) > 1
    combined = "".join(pages)
    assert "one.py" in combined
    assert "two.py" in combined
    assert combined.count("a" * 80) == 3
    assert combined.count("b" * 80) == 3


def test_diff_pages_preserves_file_context_for_oversized_single_file() -> None:
    diff = (
        "diff --git a/one.py b/one.py\n"
        "index 0000000..1111111 100644\n"
        "--- a/one.py\n"
        "+++ b/one.py\n"
        "@@ -0,0 +1,200 @@\n" + "".join(f"+line {i}\n" for i in range(200))
    )

    pages = diff_pages(diff, max_chars=200)

    assert len(pages) > 1
    assert all("diff --git a/one.py b/one.py" in page for page in pages)
    assert all(len(page.strip()) > 0 for page in pages)


def test_collect_file_blocks_splits_large_file_with_part_headers(tmp_path: Path) -> None:
    text = "".join(f"print({i})\n" for i in range(120))
    blocks = _split_source_file_blocks(Path("big.py"), "py", text, max_chars=300)

    assert len(blocks) > 1
    assert all("### File: big.py (part " in block for block in blocks)
    assert all("```py" in block for block in blocks)


def test_paginate_file_diff_block_rolling_window_overlap() -> None:
    preamble = "diff --git a/big.py b/big.py\n--- a/big.py\n+++ b/big.py\n@@ -1,100 +1,100 @@\n"
    lines = [f"+line {i:03d}\n" for i in range(100)]
    block = preamble + "".join(lines)

    windows = _paginate_file_diff_block(
        block, max_chars=500, window_size_factor=0.8, overlap_factor=0.1
    )

    assert len(windows) > 1
    assert all("diff --git a/big.py b/big.py" in w for w in windows)
    assert "line 000" in windows[0]


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
        AIConfig(provider="ollama"), request_timeout_seconds=DEFAULT_REVIEW_TIMEOUT_SECONDS
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
            "--persona",
            "devsecops",
            "--no-pre-analysis",
            "--no-static-scan",
        ],
    )
    assert res.exit_code == 0
    assert captured_kwargs.get("append_cache") is True
