"""`devops roadmap repair`: the list, the confirm and the dry run (#3478)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from devops_cli.config.constants import CONST_ROADMAP_STAGE_COMMENT_MARKER
from devops_cli.roadmap.stores.github_store import comments_endpoint, issues_endpoint, listing_path
from devops_cli.roadmap.stores.store import ItemField, RefineRecordKey
from tests.support.fakes.github import API
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

REPO = "example/roadmap"
RETURN = (
    f"{CONST_ROADMAP_STAGE_COMMENT_MARKER}\nThe stage job returned the item to New. The premise "
    "of the issue does not hold at the staging commit, so the job planned no change and opened "
    "no pull request.\n\nEvidence:\n\nNot yet: I need to inspect the repository first."
)


def _status(store: InMemoryRoadmapStore, number: int) -> str | None:
    item = store.item(number)
    assert item is not None
    return item.status


def _returned(store: InMemoryRoadmapStore, evidence_comment: str = RETURN) -> int:
    number = store.seed_issue(
        "fix(cli): a defect", body="Fix it.", fields={ItemField.PRIORITY: "P2-Medium"}
    )
    item = store.item(number)
    assert item is not None
    store.set_field(item, ItemField.STATUS, "Ready", marks={RefineRecordKey.NEXT_STEP: "ready"})
    store.comment(number, evidence_comment)
    item = store.item(number)
    assert item is not None
    store.set_field(item, ItemField.STATUS, "New")
    return number


def test_the_list_names_the_stalled_item_and_writes_nothing(
    cli: Callable[..., Any], roadmap_store: InMemoryRoadmapStore
) -> None:
    number = _returned(roadmap_store)
    writes = len(roadmap_store.job_writes())

    result = cli("roadmap", "repair", "--repo", REPO)

    assert result.exit_code == 0, result.output
    assert f"#{number} fix(cli): a defect: filler return" in result.stdout
    assert len(roadmap_store.job_writes()) == writes
    assert _status(roadmap_store, number) == "New"


def test_the_list_of_a_clean_roadmap_says_that_nothing_is_stalled(
    cli: Callable[..., Any], roadmap_store: InMemoryRoadmapStore
) -> None:
    result = cli("roadmap", "repair", "--repo", REPO)

    assert result.exit_code == 0, result.output
    assert "No item is stalled by a placeholder reply." in result.stdout


def test_a_confirm_sets_the_item_back_and_says_how_many(
    cli: Callable[..., Any], roadmap_store: InMemoryRoadmapStore
) -> None:
    number = _returned(roadmap_store)

    result = cli("roadmap", "repair", "--repo", REPO, "--confirm")

    assert result.exit_code == 0, result.output
    assert "Set back 1 item(s)." in result.output
    assert _status(roadmap_store, number) == "Ready"


def test_a_confirm_exits_1_when_an_item_fails(
    cli: Callable[..., Any], roadmap_store: InMemoryRoadmapStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    from devops_cli.exceptions import GitHubOperationError

    number = _returned(roadmap_store)

    def refuse(*_: Any, **__: Any) -> None:
        raise GitHubOperationError("GitHub answered 502.", operation="roadmap.set_field")

    monkeypatch.setattr(roadmap_store, "set_field", refuse)

    result = cli("roadmap", "repair", "--repo", REPO, "--confirm")

    assert result.exit_code == 1
    assert f"#{number}" in result.output
    assert "GitHubOperationError" in result.output


def test_the_dry_run_opens_no_store_and_lists_the_reads_and_the_writes(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    roadmap_store_repos: list[str],
) -> None:
    result = cli("roadmap", "repair", "--repo", REPO, "--dry-run")

    assert result.exit_code == 0, result.output
    assert roadmap_store_repos == []
    assert "Dry run: no request was made" in result.output
    assert f"{API}{listing_path(issues_endpoint(REPO, 'state=open'))}" in result.output
    assert comments_endpoint(REPO, 0).rsplit("/", 2)[0] in result.output
    assert "PATCH" in result.output


def test_the_dry_run_and_the_confirm_exclude_each_other(cli: Callable[..., Any]) -> None:
    assert cli("roadmap", "repair", "--repo", REPO, "--dry-run", "--confirm").exit_code == 1
