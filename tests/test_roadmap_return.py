"""`devops roadmap return`: an item goes back to New, through its `status/*` label, with an
evidence comment."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from devops_cli.exceptions import DevOpsCLIError
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.return_item import (
    ReturnPlan,
    apply_return,
    dry_run_return,
    plan_return,
    render_return_plan,
)
from devops_cli.roadmap.store import ItemField

REPO = "owner/repo"


def _item(store: InMemoryRoadmapStore, title: str, status: str) -> int:
    """An Item with Priority P2-Medium and `status`, both set as a person sets them."""
    return store.seed_issue(
        title,
        body="Cannot work",
        fields={ItemField.PRIORITY: "P2-Medium", ItemField.STATUS: status},
        labels=("type/bug",),
    )


def test_a_returned_item_is_new_with_the_evidence_comment() -> None:
    store = InMemoryRoadmapStore(repo=REPO)
    number = _item(store, "Unworkable item", "Ready")

    plan = plan_return(store, number, "  Upstream library removed this API.  ", REPO)
    apply_return(store, plan)

    returned = store.item(number)
    assert returned is not None
    assert plan == ReturnPlan(number, "Unworkable item", "Upstream library removed this API.", REPO)
    assert (returned.status, returned.labels, returned.job_record) == (
        "New",
        ("type/bug", "priority/p2-medium", "status/new"),
        {ItemField.STATUS: "New"},
    )
    assert [comment.body for comment in store.comments_on(number)] == [
        "Upstream library removed this API."
    ]


def test_the_plan_names_the_item_the_status_and_the_evidence() -> None:
    plan = ReturnPlan(7, "Flawed feature", "Evidence.", REPO)
    assert render_return_plan(plan) == (
        "Item #7: Flawed feature\nTarget Status: New\nEvidence Comment:\nEvidence."
    )


def test_an_issue_with_no_priority_is_no_item_to_return() -> None:
    store = InMemoryRoadmapStore(repo=REPO)
    number = store.seed_issue("Candidate", labels=("status/ready",))
    with pytest.raises(DevOpsCLIError, match=f"#{number} is not an item of the roadmap"):
        plan_return(store, number, "Evidence.", REPO)


def test_a_dry_run_lists_the_issue_reads_and_the_label_write() -> None:
    reads, writes = dry_run_return(REPO, 42)
    assert [request.argv for request in reads] == [("gh", "api", f"repos/{REPO}/issues/42")]
    assert [request.argv for request in writes] == [
        ("gh", "api", f"repos/{REPO}/issues/42"),
        ("gh", "api", "-X", "POST", f"repos/{REPO}/issues/42/comments", "-f", "body=<comment>"),
        ("gh", "api", f"repos/{REPO}/issues/42"),
        ("gh", "api", "-X", "PATCH", f"repos/{REPO}/issues/42", "--input", "-"),
    ]
    assert not any("project" in " ".join(request.argv) for request in [*reads, *writes])


def test_the_dry_run_command_makes_no_request(
    cli: Callable[..., Any], roadmap_store: InMemoryRoadmapStore
) -> None:
    result = cli(
        "roadmap", "return", "42", "--repo", REPO, "--comment", "Flawed premise", "--dry-run"
    )
    assert (result.exit_code, "Dry run: no request was made." in result.stdout) == (0, True)
    assert roadmap_store.job_writes() == []


def test_return_without_confirm_only_shows_the_plan(
    cli: Callable[..., Any], roadmap_store: InMemoryRoadmapStore
) -> None:
    number = _item(roadmap_store, "Flawed feature", "In Progress")
    result = cli("roadmap", "return", str(number), "--repo", REPO, "--comment", "Flawed premise")
    item = roadmap_store.item(number)
    assert item is not None
    assert (result.exit_code, "Plan only: pass --confirm to apply." in result.stdout) == (0, True)
    assert (item.status, roadmap_store.job_writes()) == ("In Progress", [])


def test_return_with_confirm_sets_new_and_posts_the_comment_file(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    roadmap_store_repos: list[str],
    tmp_path: Path,
) -> None:
    number = _item(roadmap_store, "Flawed feature", "In Progress")
    comment_file = tmp_path / "evidence.txt"
    comment_file.write_text("Detailed evidence from upstream docs.", encoding="utf-8")

    result = cli(
        "roadmap",
        "return",
        str(number),
        "--repo",
        REPO,
        "--comment-file",
        str(comment_file),
        "--confirm",
    )

    item = roadmap_store.item(number)
    assert item is not None
    assert (result.exit_code, item.status, roadmap_store_repos) == (0, "New", [REPO])
    assert [comment.body for comment in roadmap_store.comments_on(number)] == [
        "Detailed evidence from upstream docs."
    ]


def test_return_needs_an_evidence_comment(cli: Callable[..., Any]) -> None:
    result = cli("roadmap", "return", "42", "--repo", REPO)
    assert result.exit_code == 1


def test_return_takes_no_ref(cli: Callable[..., Any]) -> None:
    """Return reads no repository file, so it has no ref to read one at."""
    result = cli("roadmap", "return", "42", "--repo", REPO, "--comment", "x", "--ref", "main")
    assert result.exit_code == 2
