"""Tests for the review command group."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from devops_cli.ai.client import LLMClient
from devops_cli.ai.personas import PERSONAS, Persona
from devops_cli.commands import review
from devops_cli.commands.review import ReviewClients
from devops_cli.config.constants import CONST_REVIEW_MAX_DIFF_CHARS
from devops_cli.config.defaults import DEFAULT_REVIEW_TIMEOUT_SECONDS
from devops_cli.config.settings import AIConfig
from devops_cli.main import app
from devops_cli.models.ai import ChatMessage

runner = CliRunner()


def test_review_path_help_includes_persona_option() -> None:
    result = runner.invoke(app, ["review", "path", "--help"])

    assert result.exit_code == 0
    assert "--persona" in result.output


def test_load_agents_md_reads_repo_root_file(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "AGENTS.md").write_text("## Policy\nUse latest Python.\n", encoding="utf-8")
    nested = tmp_path / "src" / "pkg"
    nested.mkdir(parents=True)

    agents_md = review._load_agents_md(nested)

    assert "Use latest Python." in agents_md


def test_load_agents_md_returns_empty_when_missing(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)

    assert review._load_agents_md(tmp_path) == ""


def test_persona_system_prompt_includes_agents_md_when_present() -> None:
    persona = PERSONAS[Persona.DEVSECOPS]

    prompt = review._persona_system_prompt(persona, "Use latest Python by policy.")

    assert persona.system_prompt in prompt
    assert "Use latest Python by policy." in prompt
    assert "Do not raise findings that merely restate or contradict" in prompt


def test_persona_system_prompt_unchanged_when_no_agents_md() -> None:
    persona = PERSONAS[Persona.DEVSECOPS]
    prompt = review._persona_system_prompt(persona, "")

    assert prompt.startswith(persona.system_prompt)
    assert "Security & Prompt Isolation Guardrails" in prompt
    assert "Project Instructions" not in prompt


def test_collect_files_skips_gitignored_entries(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
    (tmp_path / "kept.py").write_text("print('kept')\n", encoding="utf-8")
    (tmp_path / "ignored.txt").write_text("ignore me\n", encoding="utf-8")

    subprocess.run(["git", "add", ".gitignore", "kept.py"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "-f", "ignored.txt"], cwd=tmp_path, check=True)

    content = review._collect_files(tmp_path, "*")

    assert "kept.py" in content
    assert "### ignored.txt" not in content


def test_review_prompt_contains_full_diff_without_truncation() -> None:
    big_diff = "x" * (CONST_REVIEW_MAX_DIFF_CHARS + 1)
    prompt = review._build_prompt(big_diff, "review title")

    assert "review title" in prompt
    assert big_diff in prompt


def test_paginate_blocks_keeps_small_blocks_on_one_page() -> None:
    blocks = ["a" * 10, "b" * 10, "c" * 10]

    pages = review._paginate_blocks(blocks, max_chars=1000)

    assert len(pages) == 1
    assert all(block in pages[0] for block in blocks)


def test_paginate_blocks_splits_across_pages_without_dropping_content() -> None:
    blocks = ["a" * 60, "b" * 60, "c" * 60]

    pages = review._paginate_blocks(blocks, max_chars=100)

    assert len(pages) > 1
    combined = "".join(pages)
    assert all(block in combined for block in blocks)


def test_paginate_blocks_hard_splits_an_oversized_single_block() -> None:
    huge_block = "".join(f"line-{i}\n" for i in range(60))

    pages = review._paginate_blocks([huge_block], max_chars=100)

    assert len(pages) > 1
    assert "".join(pages) == huge_block
    assert all(page.endswith("\n") for page in pages)


def test_split_diff_into_file_blocks_separates_per_file() -> None:
    diff = "diff --git a/one.py b/one.py\n+one\ndiff --git a/two.py b/two.py\n+two\n"

    blocks = review._split_diff_into_file_blocks(diff)

    assert len(blocks) == 2
    assert blocks[0].startswith("diff --git a/one.py")
    assert blocks[1].startswith("diff --git a/two.py")


def test_diff_pages_covers_every_file_when_paginated() -> None:
    diff = (
        "diff --git a/one.py b/one.py\n" + ("+" + "a" * 80 + "\n") * 3 + "diff --git a/two.py"
        " b/two.py\n" + ("+" + "b" * 80 + "\n") * 3
    )

    pages = review._diff_pages(diff, max_chars=200)

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

    pages = review._diff_pages(diff, max_chars=200)

    assert len(pages) > 1
    assert all("diff --git a/one.py b/one.py" in page for page in pages)
    assert all(len(page.strip()) > 0 for page in pages)


def test_collect_file_blocks_splits_large_file_with_part_headers(tmp_path: Path) -> None:
    text = "".join(f"print({i})\\n" for i in range(120))
    blocks = review._split_source_file_blocks(Path("big.py"), "py", text, max_chars=300)

    assert len(blocks) > 1
    assert all("### File: big.py (part " in block for block in blocks)
    assert all("```py" in block for block in blocks)


def test_run_review_three_steps_combines_segments() -> None:
    persona = PERSONAS[Persona.DEVSECOPS]
    calls: list[str] = []

    class DummyClient:
        def chat(
            self,
            system: str,
            user: str,
            *,
            enable_thinking: bool = True,
            **kwargs: object,
        ) -> str:
            calls.append(user)
            if "Per-segment review outputs" in user:
                return "final recomposed review"
            if "Be specific. Do not make recommendations." in user:
                return "summary"
            return "segment review"

    result = review._run_review(
        ["page-one", "page-two"],
        "title",
        persona,
        ReviewClients(metadata=DummyClient(), analysis=DummyClient(), compose=DummyClient()),
        agents_md="",
        build_prompt=lambda content, title: f"{title}:{content}",
    )

    # 2 review (step 2) + 1 recompose (step 3) (metadata step 1 uses fast static extraction)
    assert len(calls) == 3
    assert result == "final recomposed review"
    assert any("Review metadata for all 2 segment(s)" in c for c in calls)
    assert any("Per-segment review outputs" in c for c in calls)


def test_run_review_never_sends_empty_user_prompt() -> None:
    persona = PERSONAS[Persona.DEVSECOPS]
    calls: list[str] = []

    class DummyClient:
        def chat(
            self,
            system: str,
            user: str,
            *,
            enable_thinking: bool = True,
            **kwargs: object,
        ) -> str:
            calls.append(user)
            return "ok"

    review._run_review(
        ["content-1", "content-2"],
        "title",
        persona,
        ReviewClients(metadata=DummyClient(), analysis=DummyClient(), compose=DummyClient()),
        agents_md="",
        build_prompt=lambda content, title: f"{title}\n{content}",
    )

    # 2 review + 1 recompose
    assert len(calls) == 3
    assert all(call.strip() for call in calls)


def test_run_review_metadata_includes_filenames() -> None:
    persona = PERSONAS[Persona.DEVSECOPS]
    review_calls: list[str] = []

    class DummyClient:
        def chat(
            self,
            system: str,
            user: str,
            *,
            enable_thinking: bool = True,
            **kwargs: object,
        ) -> str:
            if "Review metadata for all" in user:
                review_calls.append(user)
            if "Per-segment review outputs" in user:
                return "done"
            if "Be specific. Do not make recommendations." in user:
                return "summary"
            return "review"

    pages = [
        "diff --git a/src/a.py b/src/a.py\n@@ -1,1 +1,2 @@\n+x\n",
        "diff --git a/src/b.py b/src/b.py\n@@ -1,1 +1,2 @@\n+y\n",
    ]
    result = review._run_review(
        pages,
        "title",
        persona,
        ReviewClients(metadata=DummyClient(), analysis=DummyClient(), compose=DummyClient()),
        agents_md="",
        build_prompt=lambda content, title: f"{title}\n{content}",
    )

    assert result == "done"
    assert len(review_calls) == 2
    assert all("src/a.py" in c for c in review_calls)
    assert all("src/b.py" in c for c in review_calls)


def test_run_review_dry_run_skips_client_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persona = PERSONAS[Persona.DEVSECOPS]
    call_count = 0

    class DummyClient:
        def chat(
            self,
            system: str,
            user: str,
            *,
            enable_thinking: bool = True,
            **kwargs: object,
        ) -> str:
            nonlocal call_count
            call_count += 1
            return "should-not-be-called"

    monkeypatch.setenv("DEVOPS_CLI_DRY_RUN", "true")

    result = review._run_review(
        ["page-one", "page-two"],
        "title",
        persona,
        ReviewClients(metadata=DummyClient(), analysis=DummyClient(), compose=DummyClient()),
        agents_md="",
        build_prompt=lambda content, title: f"{title}:{content}",
    )

    assert call_count == 0
    assert "[dry-run] Review skipped for segment 1/2." in result
    assert "[dry-run] Review skipped for segment 2/2." in result


def test_run_review_single_segment_skips_recompose() -> None:
    persona = PERSONAS[Persona.DEVSECOPS]
    calls: list[str] = []

    class DummyClient:
        def chat(
            self,
            system: str,
            user: str,
            *,
            enable_thinking: bool = True,
            **kwargs: object,
        ) -> str:
            calls.append(user)
            if "Be specific. Do not make recommendations." in user:
                return "summary"
            return "single segment review"

    result = review._run_review(
        ["only-page"],
        "title",
        persona,
        ReviewClients(metadata=DummyClient(), analysis=DummyClient(), compose=DummyClient()),
        agents_md="",
        build_prompt=lambda content, title: f"{title}:{content}",
    )

    # 1 review (step 2); step 1 uses fast static metadata extraction and step 3 (recompose) skipped
    assert len(calls) == 1
    assert result == "single segment review"
    assert "Per-segment review outputs" not in result


def test_review_client_uses_long_read_timeout_for_chat_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = LLMClient(
        AIConfig(provider="ollama"), request_timeout_seconds=DEFAULT_REVIEW_TIMEOUT_SECONDS
    )
    seen: dict[str, object] = {}

    class DummyClient:
        def __init__(self, timeout: object) -> None:
            seen["timeout"] = timeout

        def __enter__(self) -> DummyClient:
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def post(self, *args: object, **kwargs: object) -> object:
            return type(
                "Response",
                (),
                {
                    "raise_for_status": lambda self: None,
                    "json": lambda self: {"message": {"content": "ok"}},
                },
            )()

    monkeypatch.setattr("devops_cli.ai.client.httpx2.Client", DummyClient)

    client._ollama_messages("system", [ChatMessage(role="user", content="user")])

    assert seen["timeout"].read == DEFAULT_REVIEW_TIMEOUT_SECONDS
