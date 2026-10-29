"""`devops gh issues close` closes an issue with its reason, its comment first (#1658)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.store import GitHubState

REPO = "example/repo"


def _closed_as(store: InMemoryRoadmapStore, number: int) -> tuple[GitHubState, str | None]:
    found = next(issue for issue in store.issues() if issue.number == number)
    return found.state, found.state_reason


def _writes(store: InMemoryRoadmapStore) -> list[tuple[str, str | None]]:
    return [(write.operation, write.value) for write in store.job_writes()]


def _evidence(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "evidence.md"
    path.write_text(text, encoding="utf-8")
    return path


def test_a_not_planned_close_posts_the_comment_file_then_closes(
    cli: Callable[..., Any], roadmap_store: InMemoryRoadmapStore, tmp_path: Path
) -> None:
    number = roadmap_store.seed_issue("superseded")
    evidence = _evidence(tmp_path, "Superseded by #2399.\n")
    result = cli(
        "gh", "issues", "close", str(number), "--reason", "not-planned",
        "--comment-file", str(evidence), "-R", REPO,
    )  # fmt: skip
    assert (result.exit_code, _writes(roadmap_store), _closed_as(roadmap_store, number)) == (
        0,
        [("comment", "Superseded by #2399."), ("close", "not_planned")],
        (GitHubState.CLOSED, "not_planned"),
    )


def test_a_completed_close_with_no_comment_only_closes(
    cli: Callable[..., Any], roadmap_store: InMemoryRoadmapStore
) -> None:
    number = roadmap_store.seed_issue("done")
    result = cli("gh", "issues", "close", str(number), "--reason", "completed", "-R", REPO)
    assert (result.exit_code, _writes(roadmap_store), _closed_as(roadmap_store, number)) == (
        0,
        [("close", "completed")],
        (GitHubState.CLOSED, "completed"),
    )


def test_a_comment_file_of_a_dash_is_read_from_standard_input(
    cli: Callable[..., Any], roadmap_store: InMemoryRoadmapStore
) -> None:
    number = roadmap_store.seed_issue("done")
    result = cli(
        "gh", "issues", "close", str(number), "--reason", "completed",
        "--comment-file", "-", "-R", REPO,
        input="Done in #2400.\n",
    )  # fmt: skip
    assert (result.exit_code, _writes(roadmap_store)) == (
        0,
        [("comment", "Done in #2400."), ("close", "completed")],
    )


def test_an_empty_comment_is_refused_before_any_request(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    roadmap_store_repos: list[str],
    tmp_path: Path,
) -> None:
    number = roadmap_store.seed_issue("superseded")
    evidence = _evidence(tmp_path, "  \n")
    result = cli(
        "gh", "issues", "close", str(number), "--reason", "not-planned",
        "--comment-file", str(evidence), "-R", REPO,
    )  # fmt: skip
    assert (result.exit_code != 0, "empty" in result.output, roadmap_store_repos) == (
        True,
        True,
        [],
    )


def test_a_closed_issue_is_refused_with_no_write(
    cli: Callable[..., Any], roadmap_store: InMemoryRoadmapStore, tmp_path: Path
) -> None:
    number = roadmap_store.seed_issue("closed", state=GitHubState.CLOSED)
    evidence = _evidence(tmp_path, "Superseded by #2399.")
    result = cli(
        "gh", "issues", "close", str(number), "--reason", "not-planned",
        "--comment-file", str(evidence), "-R", REPO,
    )  # fmt: skip
    assert (result.exit_code != 0, "already closed" in result.output, _writes(roadmap_store)) == (
        True,
        True,
        [],
    )


def test_an_unknown_reason_exits_2_naming_the_reasons_with_no_request(
    cli: Callable[..., Any], roadmap_store_repos: list[str]
) -> None:
    result = cli("gh", "issues", "close", "7", "--reason", "wontfix", "-R", REPO)
    assert (
        result.exit_code,
        "completed" in result.output,
        "not-planned" in result.output,
        roadmap_store_repos,
    ) == (2, True, True, [])


def test_a_dry_run_lists_the_read_the_comment_and_the_close_and_sends_nothing(
    cli: Callable[..., Any], roadmap_store_repos: list[str], tmp_path: Path
) -> None:
    evidence = _evidence(tmp_path, "Superseded by #2399.")
    result = cli(
        "gh", "issues", "close", "7", "--reason", "not-planned",
        "--comment-file", str(evidence), "-R", REPO, "--dry-run",
    )  # fmt: skip
    output = " ".join(result.output.split())
    assert (
        result.exit_code,
        f"repos/{REPO}/issues/7 " in output,
        "comment on #7" in output,
        "close #7 with the reason not_planned" in output,
        '"state_reason": "not_planned"' in output,
        roadmap_store_repos,
    ) == (0, True, True, True, True, [])
