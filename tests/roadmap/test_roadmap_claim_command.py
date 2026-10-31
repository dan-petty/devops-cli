"""`devops roadmap claim` and `devops roadmap release` (#2910): the plan, the write, the refusal
and the dry run."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from devops_cli.roadmap.claim import dry_run_claim
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore

REPO = "example/roadmap"
ITEM = ("priority/p2-medium",)


def _store_item(store: InMemoryRoadmapStore, *labels: str) -> int:
    return store.seed_issue("work", labels=(*ITEM, *labels))


def _owner(store: InMemoryRoadmapStore, number: int) -> str | None:
    found = store.item(number)
    assert found is not None
    return found.owner


def test_claim_without_confirm_only_shows_the_plan(
    cli: Callable[..., Any], roadmap_store: InMemoryRoadmapStore
) -> None:
    number = _store_item(roadmap_store)
    result = cli("roadmap", "claim", str(number), "--as", "agent", "--repo", REPO)
    assert (result.exit_code, "Plan only: pass --confirm to apply." in result.stdout) == (0, True)
    assert (_owner(roadmap_store, number), roadmap_store.job_writes()) == (None, [])


def test_claim_with_confirm_sets_the_label(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    roadmap_store_repos: list[str],
) -> None:
    number = _store_item(roadmap_store)
    result = cli("roadmap", "claim", str(number), "--as", "human", "--repo", REPO, "--confirm")
    assert (result.exit_code, _owner(roadmap_store, number), roadmap_store_repos) == (
        0,
        "Human",
        [REPO],
    )


def test_claim_of_a_held_item_exits_1_and_names_the_owner(
    cli: Callable[..., Any], roadmap_store: InMemoryRoadmapStore
) -> None:
    number = _store_item(roadmap_store, "owner/human")
    result = cli("roadmap", "claim", str(number), "--as", "agent", "--repo", REPO, "--confirm")
    assert (result.exit_code, "human" in result.output, roadmap_store.job_writes()) == (
        1,
        True,
        [],
    )


def test_claim_takes_only_agent_and_human(cli: Callable[..., Any]) -> None:
    assert cli("roadmap", "claim", "7", "--as", "service", "--repo", REPO).exit_code == 2


def test_release_with_confirm_clears_the_label(
    cli: Callable[..., Any], roadmap_store: InMemoryRoadmapStore
) -> None:
    number = _store_item(roadmap_store, "owner/agent")
    result = cli("roadmap", "release", str(number), "--repo", REPO, "--confirm")
    assert (result.exit_code, _owner(roadmap_store, number)) == (0, None)


@pytest.mark.parametrize("command", [("claim", "7", "--as", "agent"), ("release", "7")])
def test_the_dry_run_makes_no_request_and_lists_the_label_write(
    cli: Callable[..., Any], roadmap_store: InMemoryRoadmapStore, command: tuple[str, ...]
) -> None:
    result = cli("roadmap", *command, "--repo", REPO, "--dry-run")
    assert (
        result.exit_code,
        "Dry run: no request was made." in result.stdout,
        "PATCH" in result.stdout,
        roadmap_store.job_writes(),
    ) == (0, True, True, [])


def test_a_dry_run_lists_the_issue_read_and_the_label_write() -> None:
    reads, writes = dry_run_claim(REPO, 42)
    assert [request.argv for request in reads] == [("gh", "api", f"repos/{REPO}/issues/42")]
    assert [request.argv for request in writes][-1] == (
        "gh",
        "api",
        "-X",
        "PATCH",
        f"repos/{REPO}/issues/42",
        "--input",
        "-",
    )
